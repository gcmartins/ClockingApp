package config

import (
	"fmt"
	"os"
	"sync"

	"github.com/joho/godotenv"
	"github.com/gcmartins/clockingapp/internal/constants"
)

// Manager holds the application configuration loaded from a .env file.
type Manager struct {
	mu     sync.RWMutex
	path   string
	values map[string]string
}

var (
	instance *Manager
	once     sync.Once
)

// GetManager returns the singleton ConfigManager, initialising it from the
// .env file in the current directory on first call.
func GetManager() *Manager {
	once.Do(func() {
		instance = &Manager{
			path:   ".env",
			values: make(map[string]string),
		}
		_ = instance.load()
	})
	return instance
}

func (m *Manager) load() error {
	m.mu.Lock()
	defer m.mu.Unlock()
	env, err := godotenv.Read(m.path)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if env != nil {
		m.values = env
	}
	return nil
}

// Get returns the value for key, or defaultVal if not set.
func (m *Manager) Get(key, defaultVal string) string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if v, ok := m.values[key]; ok {
		return v
	}
	return defaultVal
}

// Set stores key=value in memory (call Save to persist).
func (m *Manager) Set(key, value string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.values[key] = value
}

// Save writes all in-memory values to the .env file.
func (m *Manager) Save() error {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return godotenv.Write(m.values, m.path)
}

// GetAll returns a copy of all key-value pairs.
func (m *Manager) GetAll() map[string]string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := make(map[string]string, len(m.values))
	for k, v := range m.values {
		out[k] = v
	}
	return out
}

// UpdateAll replaces all values and persists them.
func (m *Manager) UpdateAll(values map[string]string) error {
	m.mu.Lock()
	m.values = values
	m.mu.Unlock()
	return m.Save()
}

// IsJiraConfigured returns (true, nil) when all Jira keys are present.
func (m *Manager) IsJiraConfigured() (bool, []string) {
	return m.checkKeys([]string{
		constants.KeyAtlassianEmail,
		constants.KeyAtlassianToken,
		constants.KeyAtlassianURL,
	})
}

// IsClockifyConfigured returns (true, nil) when all Clockify keys are present.
func (m *Manager) IsClockifyConfigured() (bool, []string) {
	return m.checkKeys([]string{
		constants.KeyClockifyWS,
		constants.KeyClockifyAPIKey,
	})
}

func (m *Manager) checkKeys(keys []string) (bool, []string) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	var missing []string
	for _, k := range keys {
		if v, ok := m.values[k]; !ok || v == "" {
			missing = append(missing, k)
		}
	}
	return len(missing) == 0, missing
}

// Validate returns an error listing any missing required keys.
func (m *Manager) Validate() error {
	_, jiraMissing := m.IsJiraConfigured()
	_, clockifyMissing := m.IsClockifyConfigured()
	all := append(jiraMissing, clockifyMissing...)
	if len(all) > 0 {
		return fmt.Errorf("missing config keys: %v", all)
	}
	return nil
}
