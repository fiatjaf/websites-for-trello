package main

import (
	"os"
	"strconv"
	"strings"
)

type Settings struct {
	Domain          string
	SitesDomain     string
	Port            string
	DatabaseURL     string
	RaygunAPIKey    string
	RedisAddr       string
	RedisPassword   string
	RedisPoolSize   int
	TrelloBotAPIKey string
	TrelloBotToken  string
}

func LoadSettings() Settings {
	redisPoolSize, err := strconv.Atoi(os.Getenv("REDIS_POOL_SIZE"))
	if err != nil {
		redisPoolSize = 6
	}

	port := os.Getenv("PORT")
	domain := os.Getenv("DOMAIN")
	if os.Getenv("DEBUG") != "" {
		domain = strings.TrimSuffix(domain, "000") + "003"
		parts := strings.Split(domain, ":")
		port = parts[1]
	}
	if port == "" {
		port = "5000"
	}

	return Settings{
		Domain:          domain,
		SitesDomain:     os.Getenv("SITES_DOMAIN"),
		Port:            port,
		DatabaseURL:     os.Getenv("DATABASE_URL"),
		RaygunAPIKey:    os.Getenv("RAYGUN_API_KEY"),
		RedisAddr:       os.Getenv("REDIS_HOST") + ":" + os.Getenv("REDIS_PORT"),
		RedisPassword:   os.Getenv("REDIS_PASSWORD"),
		RedisPoolSize:   redisPoolSize,
		TrelloBotAPIKey: os.Getenv("TRELLO_BOT_API_KEY"),
		TrelloBotToken:  os.Getenv("TRELLO_BOT_TOKEN"),
	}
}
