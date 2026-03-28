module github.com/gcmartins/clockingapp

go 1.22

require (
	github.com/joho/godotenv v1.5.1
	github.com/spf13/cobra v1.8.0
	github.com/stretchr/testify v1.9.0
)

require (
	github.com/davecgh/go-spew v1.1.1 // indirect
	github.com/inconshreveable/mousetrap v1.1.0 // indirect
	github.com/pmezard/go-difflib v1.0.0 // indirect
	github.com/spf13/pflag v1.0.5 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)

// GUI dependencies — only needed when building with -tags gui
// Run: go get fyne.io/fyne/v2@latest
// Then: go build -tags gui -o clockingapp .
//
// fyne.io/fyne/v2 v2.5.2
