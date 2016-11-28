package main

import (
	"html/template"
	"log"
	"net/http"
	"regexp"

	"github.com/carbocation/interpose"
	"github.com/carbocation/interpose/adaptors"
	"github.com/gorilla/mux"
	"github.com/hoisie/redis"
	"github.com/jmoiron/sqlx"
	"github.com/rs/cors"

	_ "github.com/lib/pq"
)

var db *sqlx.DB
var rds redis.Client
var settings Settings
var render *template.Template
var err error

func main() {
	settings = LoadSettings()

	db, err = sqlx.Connect("postgres", settings.DatabaseURL)
	if err != nil {
		log.Fatal(err)
	}
	db = db.Unsafe()
	db.SetMaxOpenConns(7)

	rds.Addr = settings.RedisAddr
	rds.Password = settings.RedisPassword
	rds.MaxPoolSize = settings.RedisPoolSize

	CardLinkMatcher = regexp.MustCompile(CARDLINKMATCHEREXPRESSION)

	render = template.Must(template.New("main").Funcs(template.FuncMap{
		"cdnurl":   cdnurl,
		"markdown": func(md string) template.HTML { return template.HTML(markdown(md)) },
	}).ParseGlob("templates/*.html"))

	// middleware
	middle := interpose.New()
	middle.Use(clearContextMiddleware)
	middle.Use(adaptors.FromNegroni(cors.New(cors.Options{
		// CORS
		AllowedOrigins: []string{"*"},
	})))

	middle.Use(func(next http.Handler) http.Handler {
		// fetch requestData
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			requestData := getRequestData(w, r)
			// when there is an error, abort and return
			// (the http status and message should have been already set at getBaseData)
			if requestData.error != nil {
				return
			}
			saveRequestData(r, requestData)
			next.ServeHTTP(w, r)
		})
	})

	middle.Use(func(next http.Handler) http.Handler {
		// try to return a standalone page
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			requestData := loadRequestData(r)
			card, err := getPageAt(requestData, r.URL.Path)
			if err != nil {
				next.ServeHTTP(w, r)
			} else {
				countPageViews(requestData)
				requestData.Card = card
				render.ExecuteTemplate(w, "card", requestData)
			}
		})
	})
	// ~

	// router
	router := mux.NewRouter()
	router.StrictSlash(true) // redirects '/path' to '/path/'
	middle.UseHandler(router)

	// > static
	router.HandleFunc("/favicon.ico", favicon)
	router.HandleFunc("/robots.txt", error404)
	router.HandleFunc("/opensearch.xml", opensearch)
	router.HandleFunc("/feed.xml", feed)

	// > redirect from permalinks
	router.HandleFunc("/c/{card-id-or-shortLink}/", cardRedirect)
	router.HandleFunc("/l/{list-id}/", listRedirect)

	// > helpers
	router.HandleFunc("/c/{card-id-or-shortLink}/desc", cardDesc)
	router.HandleFunc("/search/", handleSearch)

	// > normal pages and index
	router.HandleFunc("/p/{page:[0-9]+}/", index)
	router.HandleFunc("/tag/{label-slug}/p/{page:[0-9]+}", label)
	router.HandleFunc("/tag/{label-slug}/", label)
	router.HandleFunc("/{list-slug}/p/{page:[0-9]+}/", list)
	router.HandleFunc("/{list-slug}/{card-slug}/", card)
	router.HandleFunc("/{list-slug}/", list)
	router.HandleFunc("/", index)

	// > errors
	router.NotFoundHandler = http.HandlerFunc(error404)
	// ~

	log.Print(":: SITES :: listening at port " + settings.Port)
	http.ListenAndServe(":"+settings.Port, middle)
}
