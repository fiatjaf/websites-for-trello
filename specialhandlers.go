package main

import (
	"fmt"
	"github.com/MindscapeHQ/raygun4go"
	"github.com/gorilla/mux"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

func cardRedirect(w http.ResponseWriter, r *http.Request) {
	identifier := mux.Vars(r)["card-id-or-shortLink"]
	kind := "id"
	if len(identifier) < 15 {
		kind = "shortLink"
	}

	var slugs []string
	err := db.Select(&slugs, fmt.Sprintf(`
WITH card AS (
  SELECT name, list_id, slug, visible
  FROM cards
  WHERE "%s" = $1
)
SELECT slug FROM (
  (SELECT
    CASE WHEN "pagesList" THEN '' ELSE lists.slug END AS slug,
    0 AS listfirst
  FROM lists
  INNER JOIN card ON list_id = lists.id
  WHERE lists.visible OR "pagesList")
UNION
  (SELECT
    CASE WHEN visible THEN slug ELSE name END AS slug,
    1 AS listfirst
  FROM card)
)y
ORDER BY listfirst
    `, kind), identifier)
	if err != nil || len(slugs) != 2 {
		// redirect to the actual Trello card instead
		http.Redirect(w, r, "https://trello.com/c/"+identifier, 302)
		return
	}
	http.Redirect(w, r, "/"+slugs[0]+"/"+slugs[1]+"/", 302)
}

func listRedirect(w http.ResponseWriter, r *http.Request) {
	id := mux.Vars(r)["list-id"]

	var slug string
	err := db.Get(&slug, `
SELECT slug
FROM lists
WHERE id = $1
    `, id)
	if err != nil {
		log.Print("list not found.")
		error404(w, r)
		return
	}

	http.Redirect(w, r, "/"+slug+"/", 302)
}

func cardDesc(w http.ResponseWriter, r *http.Request) {
	identifier := mux.Vars(r)["card-id-or-shortLink"]
	kind := "id"
	if len(identifier) < 15 {
		kind = "shortLink"
	}
	qs, _ := url.ParseQuery(r.URL.RawQuery)
	var limit int
	var err error
	limit = 200
	if val, ok := qs["limit"]; ok {
		limit, err = strconv.Atoi(val[0])
		if err != nil {
			limit = 200
		}
	}

	var desc string
	err = db.Get(&desc, fmt.Sprintf(`
SELECT substring("desc" from 0 for $2)
FROM cards
WHERE "%s" = $1
    `, kind), identifier, limit)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			log.Print("there is not a card here.")
			error404(w, r)
			return
		} else {
			log.Print(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
		}
		return
	}
	fmt.Fprint(w, desc)
}

func error404(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	w.WriteHeader(404)

	query := strings.Join(filter(strings.Split(r.URL.Path, "/"), func(s string) bool {
		if s == "" {
			return false
		}
		return true
	}), " ")
	query = strings.Join(strings.Split(query, "-"), " ")

	requestData.SearchQuery = query
	requestData.TypedSearchQuery = true
	requestData.SearchResults, _ = search(query, requestData.Board.Id)

	fmt.Fprint(w,
		renderOnTopOf(requestData,
			"templates/search.html",
			"templates/404.html",
			"templates/base.html",
		),
	)
}

func opensearch(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	fmt.Fprint(w, renderOnTopOf(requestData, "templates/opensearch.xml"))
}

func favicon(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	var fav string
	if requestData.Prefs.Favicon != "" {
		fav = requestData.Prefs.Favicon
	} else {
		fav = "http://lorempixel.com/32/32/"
	}
	http.Redirect(w, r, fav, 301)
}
