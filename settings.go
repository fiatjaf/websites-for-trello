package main

import (
	"net/url"
	"os"
)

type Settings struct {
	ServiceName string
	ServiceURL  string
	Domain      string
	DatabaseURL string
}

func LoadSettings() Settings {
	serviceName := os.Getenv("SERVICE_NAME")
	if serviceName == "" {
		serviceName = "Websites for Trello"
	}

	serviceUrl := os.Getenv("SERVICE_URL")
	URL, _ := url.Parse(serviceUrl)

	return Settings{
		ServiceName: serviceName,
		ServiceURL:  serviceUrl,
		Domain:      URL.Host,
		DatabaseURL: os.Getenv("DATABASE_URL"),
	}
}
