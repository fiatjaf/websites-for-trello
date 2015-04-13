package main

import (
	"net/url"
	"os"
	"strconv"
)

type Settings struct {
	ServiceName string
	ServiceURL  string
	Domain      string
	DatabaseURL string

	RaygunAPIKey string

	RedisAddr     string
	RedisPassword string
	RedisPoolSize int
}

func LoadSettings() Settings {
	serviceName := os.Getenv("SERVICE_NAME")
	if serviceName == "" {
		serviceName = "Websites for Trello"
	}

	serviceUrl := os.Getenv("SERVICE_URL")
	URL, _ := url.Parse(serviceUrl)

	redisURL, _ := url.Parse(os.Getenv("REDISCLOUD_URL"))
	redisPoolSize, err := strconv.Atoi(os.Getenv("REDIS_POOL_SIZE"))
	if err != nil {
		redisPoolSize = 8
	}
	redisPassword, _ := redisURL.User.Password()

	return Settings{
		ServiceName: serviceName,
		ServiceURL:  serviceUrl,
		Domain:      URL.Host,
		DatabaseURL: os.Getenv("DATABASE_URL"),

		RaygunAPIKey: os.Getenv("RAYGUN_API_KEY"),

		RedisAddr:     redisURL.Host,
		RedisPassword: redisPassword,
		RedisPoolSize: redisPoolSize,
	}
}
