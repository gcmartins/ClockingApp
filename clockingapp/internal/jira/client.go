package jira

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"github.com/gcmartins/clockingapp/internal/config"
	"github.com/gcmartins/clockingapp/internal/constants"
	"github.com/gcmartins/clockingapp/internal/models"
)

// Client calls the Jira REST API v3 using basic auth (email + API token).
type Client struct {
	email    string
	token    string
	baseURL  string
	http     *http.Client
	projCache sync.Map // string → string
}

// NewClient creates an authenticated Jira client from .env credentials.
func NewClient() (*Client, error) {
	cfg := config.GetManager()
	ok, missing := cfg.IsJiraConfigured()
	if !ok {
		return nil, fmt.Errorf("Jira not configured; missing keys: %v", missing)
	}
	return &Client{
		email:   cfg.Get(constants.KeyAtlassianEmail, ""),
		token:   cfg.Get(constants.KeyAtlassianToken, ""),
		baseURL: cfg.Get(constants.KeyAtlassianURL, ""),
		http:    &http.Client{Timeout: 15 * time.Second},
	}, nil
}

// GetOpenIssues fetches issues assigned to the authenticated user that have an open status.
func (c *Client) GetOpenIssues() ([]models.Task, error) {
	jql := fmt.Sprintf(`assignee = "%s" ORDER BY updated DESC`, c.email)
	url := fmt.Sprintf("%s/rest/api/3/search?jql=%s&maxResults=100&fields=summary,status",
		c.baseURL, jql)

	var result struct {
		Issues []struct {
			Key    string `json:"key"`
			Fields struct {
				Summary string `json:"summary"`
				Status  struct {
					Name string `json:"name"`
				} `json:"status"`
			} `json:"fields"`
		} `json:"issues"`
	}
	if err := c.get(url, &result); err != nil {
		return nil, fmt.Errorf("fetching Jira issues: %w", err)
	}

	openSet := make(map[string]bool, len(constants.JiraOpenStatuses))
	for _, s := range constants.JiraOpenStatuses {
		openSet[s] = true
	}

	var tasks []models.Task
	for _, issue := range result.Issues {
		if openSet[issue.Fields.Status.Name] {
			tasks = append(tasks, models.Task{
				Key:         issue.Key,
				Description: issue.Fields.Summary,
			})
		}
	}
	return tasks, nil
}

// PushWorklog adds a worklog entry to the given issue key.
func (c *Client) PushWorklog(issueKey string, start time.Time, duration time.Duration) error {
	seconds := int(duration.Seconds())
	if seconds < 60 {
		return fmt.Errorf("worklog duration too short: %s", duration)
	}

	payload := map[string]interface{}{
		"timeSpentSeconds": seconds,
		"started":          start.Format("2006-01-02T15:04:05.000-0700"),
	}
	url := fmt.Sprintf("%s/rest/api/3/issue/%s/worklog", c.baseURL, issueKey)
	body, _ := json.Marshal(payload)

	var resp struct{}
	return c.post(url, body, &resp)
}

// GetProjectName returns the display name for a project key (cached).
func (c *Client) GetProjectName(projectKey string) (string, error) {
	if name, ok := c.projCache.Load(projectKey); ok {
		return name.(string), nil
	}
	url := fmt.Sprintf("%s/rest/api/3/project/%s", c.baseURL, projectKey)
	var project struct {
		Name string `json:"name"`
	}
	if err := c.get(url, &project); err != nil {
		return "", fmt.Errorf("fetching project %s: %w", projectKey, err)
	}
	c.projCache.Store(projectKey, project.Name)
	return project.Name, nil
}

func (c *Client) get(url string, out interface{}) error {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	req.SetBasicAuth(c.email, c.token)
	req.Header.Set("Accept", "application/json")
	return c.do(req, out)
}

func (c *Client) post(url string, body []byte, out interface{}) error {
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.SetBasicAuth(c.email, c.token)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	return c.do(req, out)
}

func (c *Client) do(req *http.Request, out interface{}) error {
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return fmt.Errorf("Jira HTTP %d: %s", resp.StatusCode, string(data))
	}
	if out != nil {
		return json.Unmarshal(data, out)
	}
	return nil
}
