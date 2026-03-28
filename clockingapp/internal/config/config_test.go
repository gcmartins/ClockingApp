package config

import (
	"os"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// newTestManager creates an isolated Manager for testing without touching the singleton.
func newTestManager(t *testing.T) *Manager {
	t.Helper()
	f, err := os.CreateTemp(t.TempDir(), ".env")
	require.NoError(t, err)
	f.Close()
	return &Manager{path: f.Name(), values: make(map[string]string)}
}

func TestGetSet(t *testing.T) {
	m := newTestManager(t)
	assert.Equal(t, "default", m.Get("MISSING_KEY", "default"))
	m.Set("FOO", "bar")
	assert.Equal(t, "bar", m.Get("FOO", ""))
}

func TestSaveAndLoad(t *testing.T) {
	m := newTestManager(t)
	m.Set("KEY1", "value1")
	m.Set("KEY2", "value2")
	require.NoError(t, m.Save())

	m2 := &Manager{path: m.path, values: make(map[string]string)}
	require.NoError(t, m2.load())
	assert.Equal(t, "value1", m2.Get("KEY1", ""))
	assert.Equal(t, "value2", m2.Get("KEY2", ""))
}

func TestIsJiraConfigured_Missing(t *testing.T) {
	m := newTestManager(t)
	ok, missing := m.IsJiraConfigured()
	assert.False(t, ok)
	assert.Len(t, missing, 3)
}

func TestIsJiraConfigured_Present(t *testing.T) {
	m := newTestManager(t)
	m.Set("ATLASSIAN_EMAIL", "a@b.com")
	m.Set("ATLASSIAN_TOKEN", "token")
	m.Set("ATLASSIAN_URL", "https://x.atlassian.net")
	ok, missing := m.IsJiraConfigured()
	assert.True(t, ok)
	assert.Empty(t, missing)
}

func TestIsClockifyConfigured_Missing(t *testing.T) {
	m := newTestManager(t)
	ok, missing := m.IsClockifyConfigured()
	assert.False(t, ok)
	assert.Len(t, missing, 2)
}

func TestConcurrentAccess(t *testing.T) {
	m := newTestManager(t)
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			m.Set("KEY", "value")
			_ = m.Get("KEY", "")
		}(i)
	}
	wg.Wait()
}

func TestUpdateAll(t *testing.T) {
	m := newTestManager(t)
	err := m.UpdateAll(map[string]string{"A": "1", "B": "2"})
	require.NoError(t, err)
	assert.Equal(t, "1", m.Get("A", ""))
	assert.Equal(t, "2", m.Get("B", ""))
}
