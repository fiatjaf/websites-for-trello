package main

import (
	"fmt"
	"github.com/MindscapeHQ/raygun4go"
	"github.com/carbocation/interpose"
	"github.com/carbocation/interpose/adaptors"
	"github.com/gorilla/mux"
	"github.com/hoisie/redis"
	"github.com/jabley/mustache"
	"github.com/jmoiron/sqlx"
	"github.com/jmoiron/sqlx/types"
	"github.com/rs/cors"
	"log"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	_ "github.com/lib/pq"
)

var db *sqlx.DB
var rds redis.Client
var settings Settings
var context BaseData

func getBaseData(w http.ResponseWriter, r *http.Request) BaseData {
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	var identifier string
	var board Board

	// board and author
	if strings.HasSuffix(r.Host, settings.Domain) {
		// subdomain
		identifier = strings.Split(r.Host, ".")[0]
		err = db.Get(&board, `
SELECT boards.id, name, boards.desc, users.id AS user_id, "avatarHash", "gravatarHash", users.bio
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
		if err.Error() == "sql: no rows in result set" {
			// don't report to raygun, we already know the error and it doesn't matter
			http.Error(w, "We don't have the site "+identifier+" here.", 404)
			return BaseData{error: err}
		} else {
			log.Print(err)
			raygun.CreateError(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return BaseData{error: err}
		}
	}

	// lists for <nav>
	var lists []List
	err = db.Select(&lists, `
SELECT id, name, slug
FROM lists
WHERE visible = true
  AND board_id = $1
  AND closed = false
ORDER BY pos
    `, board.Id)
	if err != nil {
		log.Print(err)
		http.Error(w, "There was an error in the process of fetching data for "+identifier+" from Trello, or this process was aborted by the Board owner. If you are the Board owner, try updating the Board somehow, maybe changing its description, or try to re-enable the same Board from our dashboard.", 500)
		return BaseData{error: err}
	}

	// prefs
	var jsonPrefs types.JsonText
	err = db.Get(&jsonPrefs, "SELECT preferences($1)", identifier)
	if err != nil {
		log.Print(err)
		raygun.CreateError(err.Error())
		http.Error(w, "A strange error ocurred. If you are the Board owner for this site, please report it to us. It is probably an error with the _preferences List.", 500)
		return BaseData{error: err}
	}
	var prefs Preferences
	err = jsonPrefs.Unmarshal(&prefs)
	if err != nil {
		log.Print(err)
		raygun.CreateError(err.Error())
		http.Error(w, err.Error(), 500)
		return BaseData{error: err}
	}

	// pagination
	page := 1
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err = strconv.Atoi(val)
		if err != nil {
			log.Print(err)
			raygun.CreateError(err.Error())
			http.Error(w, val+" is not a page number.", 400)
			return BaseData{error: err}
		}
	}
	hasPrev := false
	if page > 1 {
		hasPrev = true
	}

	return BaseData{
		Settings: settings,
		Board:    board,
		Lists:    lists,
		Prefs:    prefs,
		Page:     page,
		HasPrev:  hasPrev,
	}
}

func getPageAt(path string) (Card, error) {
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	defer raygun.HandleError()
	// ~

	pathAlt := strings.TrimSuffix(path, "/")
	if path == pathAlt {
		pathAlt = path + "/"
	}

	// fetch card from standalone pages
	var card Card
	err = db.Get(&card, `
SELECT cards.slug,
       cards.name,
       coalesce(cards."pageTitle", '') as "pageTitle",
       cards.desc,
       cards.attachments,
       cards.checklists,
       coalesce(cards.cover, '') AS cover
FROM cards
INNER JOIN lists ON lists.id = cards.list_id
INNER JOIN boards ON boards.id = lists.board_id
WHERE boards.id = $1
  AND lists."pagesList"
  AND cards.name IN ($2, $3)
`, context.Board.Id, path, pathAlt)
	log.Print(err)
	if err != nil {
		// this error doesn't matter, since in the majority of cases there will be nothing here anyway.
		return card, err
	}
	card.IsPage = true
	return card, nil
}

func index(w http.ResponseWriter, r *http.Request) {
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	context.Page = 1
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil || page < 0 {
			log.Print(err)
			raygun.CreateError(err.Error())
			http.Error(w, val+" is not a page number.", 400)
			return
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
	db.Select(&cards, `
SELECT cards.slug,
       cards.name,
       coalesce(cards.cover, '') as cover,
       cards.id,
       due,
       list_id
FROM cards
INNER JOIN lists ON lists.id = cards.list_id
WHERE lists.board_id = $1
  AND lists.visible = true
  AND cards.visible = true
ORDER BY cards.due DESC, cards.id DESC
OFFSET $2
LIMIT $3
    `, context.Board.Id, ppp*(context.Page-1), ppp+1)
	if err != nil {
		log.Print(err)
		raygun.CreateError(err.Error())
		http.Error(w, err.Error(), 500)
		return
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
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	ppp := context.Prefs.PostsPerPage()
	listSlug := mux.Vars(r)["list-slug"]

	// fetch home cards for this list
	var cards []Card
	db.Select(&cards, `
(
  SELECT slug,
         name,
         null AS due,
         id,
         0 AS pos,
         '' AS cover
  FROM lists
  WHERE board_id = $1
    AND slug = $2
    AND visible
) UNION ALL (
  SELECT cards.slug,
         cards.name,
         cards.due,
         cards.id,
         cards.pos,
         coalesce(cards.cover, '') AS cover
  FROM cards
  INNER JOIN lists
  ON lists.id = cards.list_id
  WHERE board_id = $1
    AND lists.slug = $2
    AND cards.visible
  OFFSET $3
  LIMIT $4
)
ORDER BY pos
    `, context.Board.Id, listSlug, ppp*(context.Page-1), ppp+1)

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

func cardRedirect(w http.ResponseWriter, r *http.Request) {
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// from_list/list-id/card-id/
	vars := mux.Vars(r)
	listId := vars["list-id"]
	cardSlug := vars["card-slug"]

	// get list slug
	var listSlug string
	err = db.Get(&listSlug, "SELECT slug FROM lists WHERE id = $1", listId)
	if err != nil {
		log.Print(err)
		// do not report this to raygun since it is just a 404
		http.Error(w, "there is not a "+listId+" list.", 404)
		return
	}

	http.Redirect(w, r, "/"+listSlug+"/"+cardSlug+"/", 302)
}

func shortLinkRedirect(w http.ResponseWriter, r *http.Request) {
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// from_shortLink/shortLink/
	shortLink := mux.Vars(r)["shortLink"]

	// get entity -- list or card
	var path string
	err = db.Get(&path, `
SELECT CASE
  WHEN lists."pagesList" THEN cards.name
  ELSE '/' || lists.slug || '/' || cards.slug
END AS path
FROM cards
INNER JOIN lists on cards.list_id = lists.id
WHERE cards."shortLink" = $1`, shortLink)
	if err != nil {
		log.Print(err)
		// redirect to the actual Trello card instead
		http.Redirect(w, r, "https://trello.com/c/"+shortLink, 302)
		return
	}

	http.Redirect(w, r, path, 302)
}

func card(w http.ResponseWriter, r *http.Request) {
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	vars := mux.Vars(r)
	listSlug := vars["list-slug"]
	cardSlug := vars["card-slug"]

	// fetch this card and its parent list
	var cards []Card
	err = db.Select(&cards, `
SELECT slug, name, due, id, "desc", attachments, checklists, cover
FROM (
  (
    SELECT slug,
           name,
           null AS due,
           id,
           '' AS "desc",
           '""'::jsonb AS attachments,
           '""'::jsonb AS checklists,
           0 AS sort,
           '' AS cover
    FROM lists
    WHERE board_id = $1
      AND slug = $2
      AND visible
  ) UNION ALL (
    SELECT cards.slug,
           cards.name,
           cards.due,
           cards.id,
           cards.desc,
           cards.attachments,
           cards.checklists,
           1 AS sort,
           coalesce(cards.cover, '') AS cover
    FROM cards
    INNER JOIN lists
    ON lists.id = cards.list_id
    WHERE cards.slug = $3
      AND lists.slug = $2
      AND cards.visible
  )
) AS u
ORDER BY sort
	`, context.Board.Id, listSlug, cardSlug)
	if err != nil {
		log.Print(err)
		// do not report this to raygun since it is just a 404
		http.Error(w, "there is not a card here.", 404)
		return
	}

	// the first row is a List dressed as a Card
	list := List{
		Name: cards[0].Name,
		Slug: cards[0].Slug,
	}
	context.List = list
	context.Card = cards[1]

	fmt.Fprint(w,
		mustache.RenderFileInLayout("templates/card.html",
			"templates/base.html",
			context),
	)
}

func favicon(w http.ResponseWriter, r *http.Request) {
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	var fav string
	if context.Prefs.Favicon != "" {
		fav = context.Prefs.Favicon
	} else {
		fav = "http://lorempixel.com/32/32/"
	}
	http.Redirect(w, r, fav, 301)
}

func httpError(code int) func(w http.ResponseWriter, r *http.Request) {
	return func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "Not found.", 404)
	}
}

func main() {
	settings = LoadSettings()

	db, _ = sqlx.Connect("postgres", settings.DatabaseURL)
	db = db.Unsafe()

	rds.Addr = settings.RedisAddr
	rds.Password = settings.RedisPassword
	rds.MaxPoolSize = settings.RedisPoolSize

	CardLinkMatcher = regexp.MustCompile(CardLinkMatcherExpression)

	// middleware
	middle := interpose.New()
	middle.Use(adaptors.FromNegroni(cors.New(cors.Options{
		// CORS
		AllowedOrigins: []string{"*"},
	})))
	middle.Use(func(next http.Handler) http.Handler {
		// fetch context
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			context = getBaseData(w, r)
			// when there is an error, abort and return
			// (the http status and message should have been already set at getBaseData)
			if context.error != nil {
				return
			}
			next.ServeHTTP(w, r)
		})
	})
	middle.Use(func(next http.Handler) http.Handler {
		// count access on redis
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			year, month, _ := time.Now().Date()
			key := fmt.Sprintf("views:%d-%d", year, month)
			board := fmt.Sprintf("%s", context.Board.Id)
			rds.Hincrby(key, board, 1)
			next.ServeHTTP(w, r)
		})
	})
	middle.Use(func(next http.Handler) http.Handler {
		// try to return a standalone page
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			card, err := getPageAt(r.URL.Path)
			if err != nil {
				next.ServeHTTP(w, r)
			} else {
				context.Card = card
				fmt.Fprint(w,
					mustache.RenderFileInLayout("templates/card.html",
						"templates/base.html",
						context),
				)
			}
		})
	})
	// ~

	router := mux.NewRouter()
	router.StrictSlash(true) // redirects '/path' to '/path/'
	middle.UseHandler(router)

	router.HandleFunc("/favicon.ico", favicon)
	router.HandleFunc("/robots.txt", httpError(404))
	router.HandleFunc("/p/{page:[0-9]+}/", index)
	router.HandleFunc("/{list-slug}/p/{page:[0-9]+}/", list)
	router.HandleFunc("/from_shortLink/{shortLink}/", shortLinkRedirect)
	router.HandleFunc("/from_list/{list-id}/{card-slug}/", cardRedirect)
	router.HandleFunc("/{list-slug}/{card-slug}/", card)
	router.HandleFunc("/{list-slug}/", list)
	router.HandleFunc("/", index)

	port := os.Getenv("PORT")
	if port == "" {
		port = "5000"
	}
	log.Print("listening...")
	http.ListenAndServe(":"+port, middle)
}
