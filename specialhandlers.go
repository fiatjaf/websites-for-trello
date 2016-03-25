package main

import (
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	log "github.com/Sirupsen/logrus"
	"github.com/gorilla/feeds"
	"github.com/gorilla/mux"
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
		log.WithFields(log.Fields{
			"listId": id,
			"err":    err.Error(),
		}).Warn("couldn't redirect to list")
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

	var fav string
	if requestData.Prefs.Favicon != "" {
		fav = requestData.Prefs.Favicon
	} else {
		fav = "https://avatars3.githubusercontent.com/u/13661927?v=3&s=200"
	}
	http.Redirect(w, r, fav, 301)
}

func handleSearch(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	countPageViews(requestData)

	values := r.URL.Query()
	query := values.Get("query")

	requestData.SearchQuery = query
	requestData.TypedSearchQuery = query != ""
	requestData.SearchResults, _ = search(query, requestData.Board.Id)
	fmt.Fprint(w,
		renderOnTopOf(requestData,
			"templates/search.html",
			"templates/base.html",
		),
	)
}

func feed(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)

	var cards []Card
	err := db.Select(&cards, `
SELECT cards.slug,
       cards.name,
       cards.desc,
       cards.id,
       CASE WHEN due IS NOT NULL THEN due ELSE (to_timestamp(hex_to_int(left(cards.id, 8)))) END AS due,
       list_id,
       coalesce(cards.cover, '') AS cover,
       cards.attachments->'attachments' AS attachments
FROM cards
INNER JOIN lists ON lists.id = cards.list_id
WHERE lists.board_id = $1
  AND lists.visible
  AND cards.visible
ORDER BY due DESC
LIMIT 30
    `, requestData.Board.Id)
	if err != nil {
		log.Print(err)
		w.WriteHeader(500)
		return
	}

	if len(cards) == 0 {
		w.WriteHeader(http.StatusNoContent)
		return
	}

	// generate feed
	feed := &feeds.Feed{
		Title:       requestData.Board.Name,
		Link:        &feeds.Link{Href: "http://" + r.Host + "/"},
		Description: requestData.Board.Desc,
		Author:      &feeds.Author{Name: requestData.Board.Name, Email: "websitesfortrello@boardthreads.com"},
		Created:     cards[0].Date(),
	}
	feed.Items = []*feeds.Item{}
	for _, card := range cards {
		feed.Items = append(feed.Items, &feeds.Item{
			Id:          "http://" + r.Host + "/c/" + card.Id,
			Title:       card.Name,
			Link:        &feeds.Link{Href: "http://" + r.Host + "/c/" + card.Id},
			Description: card.DescRender(),
			Created:     card.Date(),
		})
	}
	rss, err := feed.ToRss()
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	fmt.Fprint(w, rss)
}

func hfeed(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)

	// fetch a lot of links for displaying here
	// we have to manually modify preferences to ensure this.
	requestData.Prefs.ExcerptsValue = "0"
	requestData.Prefs.PostsPerPageValue = "25"

	err := completeWithIndexCards(&requestData)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	fmt.Fprint(w,
		renderOnTopOf(requestData,
			"templates/h-feed.html",
		),
	)
}
