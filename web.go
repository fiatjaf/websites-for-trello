package main

import (
	"fmt"
	"github.com/gorilla/mux"
	"github.com/jabley/mustache"
	"github.com/jmoiron/sqlx"
	"github.com/jmoiron/sqlx/types"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"

	_ "github.com/lib/pq"
)

var db *sqlx.DB
var settings Settings

func getBaseData(r *http.Request) BaseData {
	var err error
	var identifier string

	var board Board
	var author Author

	// board and author
	if strings.HasSuffix(r.Host, settings.Domain) {
		// subdomain
		identifier = strings.Split(r.Host, ".")[0]
		err = db.Get(&board, `
SELECT boards.id, name, boards.desc, users.id AS user_id, 'avatarHash', 'gravatarHash', users.bio
FROM boards
INNER JOIN users ON users.id = boards.user_id
WHERE subdomain = $1`,
			identifier)
	} else {
		// domain
		identifier = r.Host
		err = db.Get(&board, `
SELECT boards.id, name, boards.desc, users.id AS user_id, 'avatarHash', 'gravatarHash', users.bio
FROM boards
INNER JOIN custom_domains ON custom_domains.board_id = boards.id
INNER JOIN users ON users.id = boards.user_id
WHERE custom_domains.domain = $1`,
			identifier)
	}
	if err != nil {
		log.Fatal(err)
	}

	// lists for <nav>
	var lists []List
	err = db.Select(&lists, `
SELECT id, name, slug
FROM lists
WHERE visible = true AND board_id = $1
ORDER BY pos
    `, board.Id)
	if err != nil {
		log.Fatal(err)
	}

	// prefs
	var jsonPrefs types.JsonText
	err = db.Get(&jsonPrefs, "SELECT preferences($1)", identifier)
	if err != nil {
		log.Fatal(err)
	}
	var prefs Preferences
	err = jsonPrefs.Unmarshal(&prefs)
	if err != nil {
		log.Fatal(err)
	}

	// pagination
	page := 1
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err = strconv.Atoi(val)
		if err != nil {
			log.Fatal(err)
		}
	}
	hasPrev := false
	if page > 1 {
		hasPrev = true
	}

	return BaseData{
		Settings: settings,
		Board:    board,
		Author:   author,
		Lists:    lists,
		Prefs:    prefs,
		Page:     page,
		HasPrev:  hasPrev,
	}
}

func index(w http.ResponseWriter, r *http.Request) {
	context := getBaseData(r)

	context.Page = 1
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil {
			log.Fatal(err)
		}
		context.Page = page
	}
	if context.Page > 1 {
		context.HasPrev = true
	} else {
		context.HasPrev = false
	}

	ppp := context.Prefs.PostsPerPage()

	// fetch home cards for home
	var cards []Card
	err := db.Select(&cards, `
SELECT cards.slug, cards.name, coalesce(cards.cover, '') as cover, cards.created_on, due, list_id
FROM cards
INNER JOIN lists ON lists.id = cards.list_id
WHERE lists.board_id = $1
  AND lists.visible = true
  AND cards.visible = true
ORDER BY cards.due DESC, cards.created_on DESC
OFFSET $2
LIMIT $3
    `, context.Board.Id, ppp*(context.Page-1), ppp+1)
	if err != nil {
		log.Fatal(err)
	}

	if len(cards) > ppp {
		context.HasNext = true
		cards = cards[:ppp]
	} else {
		context.HasNext = false
	}

	context.Cards = cards

	fmt.Fprint(w,
		mustache.RenderFileInLayout("templates/list.html",
			"templates/base.html",
			context),
	)
}

func list(w http.ResponseWriter, r *http.Request) {
	context := getBaseData(r)

	ppp := context.Prefs.PostsPerPage()
	listSlug := mux.Vars(r)["list-slug"]

	// fetch home cards for this list
	var cards []Card
	err := db.Select(&cards, `
(
  SELECT slug, name, null AS due, created_on, 0 AS pos, '' AS cover
  FROM lists
  WHERE board_id = $1
    AND slug = $2
    AND visible
) UNION ALL (
  SELECT cards.slug, cards.name, cards.due, cards.created_on, cards.pos, coalesce(cards.cover, '') AS cover
  FROM cards
  INNER JOIN lists
  ON lists.id = cards.list_id
  WHERE lists.slug = $2
    AND cards.visible
  OFFSET $3
  LIMIT $4
)
ORDER BY pos
    `, context.Board.Id, listSlug, ppp*(context.Page-1), ppp+1)
	if err != nil {
		log.Fatal(err)
	}

	// the first row is a List dressed as a Card
	list := List{
		Name: cards[0].Name,
		Slug: cards[0].Slug,
	}
	cards = cards[1:]

	if len(cards) > ppp {
		context.HasNext = true
		cards = cards[:ppp]
	} else {
		context.HasNext = false
	}

	context.List = list
	context.Cards = cards

	fmt.Fprint(w,
		mustache.RenderFileInLayout("templates/list.html",
			"templates/base.html",
			context),
	)
}

func main() {
	settings = LoadSettings()

	db, _ = sqlx.Connect("postgres", settings.DatabaseURL)
	db = db.Unsafe()

	router := mux.NewRouter()
	router.StrictSlash(true) // redirects '/path' to '/path/'

	router.HandleFunc("/{page:[0-9]+}/", index)
	router.HandleFunc("/", index)
	router.HandleFunc("/{list-slug}/{page:[0-9]+}/", list)
	router.HandleFunc("/{list-slug}/", list)
	router.HandleFunc("/{list-slug}/{card-slug}/", list)

	http.Handle("/", router)

	port := os.Getenv("PORT")
	if port == "" {
		port = "5000"
	}
	log.Print("listening...")
	http.ListenAndServe(":"+port, nil)
}
