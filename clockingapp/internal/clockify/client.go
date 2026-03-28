package clockify

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gcmartins/clockingapp/internal/config"
	"github.com/gcmartins/clockingapp/internal/constants"
)

const baseURL = "https://api.clockify.me/api/v1"

// Client holds auth info and caches for Clockify API calls.
type Client struct {
	apiKey      string
	workspaceID string
	http        *http.Client

	projectCache sync.Map // string → string (name → id)
	taskCache    sync.Map // string → string (projectID+":"+name → taskID)
}

// NewClient creates a Clockify client from the config manager credentials.
func NewClient() (*Client, error) {
	cfg := config.GetManager()
	ok, missing := cfg.IsClockifyConfigured()
	if !ok {
		return nil, fmt.Errorf("Clockify not configured; missing keys: %v", missing)
	}
	return &Client{
		apiKey:      cfg.Get(constants.KeyClockifyAPIKey, ""),
		workspaceID: cfg.Get(constants.KeyClockifyWS, ""),
		http:        &http.Client{Timeout: 15 * time.Second},
	}, nil
}

// PushWorklog logs a time entry in Clockify for the given task key.
// The project key is derived from the task key (e.g. "PROJ" from "PROJ-123").
func (c *Client) PushWorklog(taskKey string, start, end time.Time) error {
	parts := strings.SplitN(taskKey, "-", 2)
	projectKey := parts[0]

	projectID, err := c.findProject(projectKey)
	if err != nil {
		return fmt.Errorf("finding Clockify project %q: %w", projectKey, err)
	}

	taskID, err := c.findOrCreateTask(projectID, taskKey)
	if err != nil {
		return fmt.Errorf("finding/creating Clockify task %q: %w", taskKey, err)
	}

	return c.logTime(projectID, taskID, taskKey, start, end)
}

func (c *Client) findProject(name string) (string, error) {
	if id, ok := c.projectCache.Load(name); ok {
		return id.(string), nil
	}

	url := fmt.Sprintf("%s/workspaces/%s/projects?name=%s&strict-name-search=true",
		baseURL, c.workspaceID, name)
	var projects []struct {
		ID   string `json:"id"`
		Name string `json:"name"`
	}
	if err := c.get(url, &projects); err != nil {
		return "", err
	}
	if len(projects) == 0 {
		return "", fmt.Errorf("project %q not found in Clockify", name)
	}
	id := projects[0].ID
	c.projectCache.Store(name, id)
	return id, nil
}

func (c *Client) findOrCreateTask(projectID, taskName string) (string, error) {
	cacheKey := projectID + ":" + taskName
	if id, ok := c.taskCache.Load(cacheKey); ok {
		return id.(string), nil
	}

	// Try to find existing task
	url := fmt.Sprintf("%s/workspaces/%s/projects/%s/tasks",
		baseURL, c.workspaceID, projectID)
	var tasks []struct {
		ID   string `json:"id"`
		Name string `json:"name"`
	}
	if err := c.get(url, &tasks); err != nil {
		return "", err
	}
	for _, t := range tasks {
		if t.Name == taskName {
			c.taskCache.Store(cacheKey, t.ID)
			return t.ID, nil
		}
	}

	// Create new task
	body, _ := json.Marshal(map[string]string{"name": taskName})
	var created struct {
		ID string `json:"id"`
	}
	if err := c.post(url, body, &created); err != nil {
		return "", fmt.Errorf("creating task %q: %w", taskName, err)
	}
	c.taskCache.Store(cacheKey, created.ID)
	return created.ID, nil
}

func (c *Client) logTime(projectID, taskID, taskKey string, start, end time.Time) error {
	payload := map[string]interface{}{
		"start":       start.UTC().Format(constants.DateTimeFmt),
		"end":         end.UTC().Format(constants.DateTimeFmt),
		"billable":    "true",
		"description": taskKey,
		"projectId":   projectID,
		"taskId":      taskID,
	}
	url := fmt.Sprintf("%s/workspaces/%s/time-entries", baseURL, c.workspaceID)
	body, _ := json.Marshal(payload)
	var resp struct{}
	return c.post(url, body, &resp)
}

func (c *Client) get(url string, out interface{}) error {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-Api-Key", c.apiKey)
	return c.do(req, out)
}

func (c *Client) post(url string, body []byte, out interface{}) error {
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("X-Api-Key", c.apiKey)
	req.Header.Set("Content-Type", "application/json")
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
		return fmt.Errorf("Clockify HTTP %d: %s", resp.StatusCode, string(data))
	}
	if out != nil {
		return json.Unmarshal(data, out)
	}
	return nil
}
