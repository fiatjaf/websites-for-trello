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
	}
	if port == "" {
		parts := strings.Split(domain, ":")
		port = parts[1]
		port = "4500"
	}

	return Settings{
		Domain:          domain,
		SitesDomain:     os.Getenv("SITES_DOMAIN"),
		Port:            port,
		DatabaseURL:     os.Getenv("DATABASE_URL"),
		RedisAddr:       os.Getenv("REDIS_HOST") + ":" + os.Getenv("REDIS_PORT"),
		RedisPassword:   os.Getenv("REDIS_PASSWORD"),
		RedisPoolSize:   redisPoolSize,
		TrelloBotAPIKey: os.Getenv("TRELLO_BOT_API_KEY"),
		TrelloBotToken:  os.Getenv("TRELLO_BOT_TOKEN"),
	}
}
