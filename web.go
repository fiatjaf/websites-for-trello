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
	"net/url"
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

func countPageViews() {
	now := time.Now().UTC()
	key := fmt.Sprintf("pageviews:%d:%d:%s", now.Year(), int(now.Month()), context.Board.Id)
	rds.Incr(key)
}

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
WHERE subdomain = lower($1)`,
			identifier)
	} else {
		// domain
		identifier = r.Host
		err = db.Get(&board, `
SELECT boards.id, name, boards.desc, users.id AS user_id, "avatarHash", "gravatarHash", users.bio
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
			log.Print(err.Error())
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
WHERE board_id = $1
  AND visible
  AND NOT closed
ORDER BY pos
    `, board.Id)
	if err != nil {
		log.Print(err)
		raygun.CreateError(err.Error())
		http.Error(w, "There was an error in the process of fetching data for "+identifier+" from Trello, or this process was aborted by the Board owner. If you are the Board owner, try to re-setup the same Board from our dashboard.", 500)
		return BaseData{error: err}
	}

	// prefs
	var jsonPrefs types.JsonText
	err = db.Get(&jsonPrefs, "SELECT preferences($1)", identifier)
	if err != nil {
		log.Print(err.Error())
		raygun.CreateError(err.Error())
		http.Error(w, "A strange error ocurred. If you are the Board owner for this site, please report it to us. It is probably an error with the _preferences List.", 500)
		return BaseData{error: err}
	}
	var prefs Preferences
	err = jsonPrefs.Unmarshal(&prefs)
	if err != nil {
		log.Print(err.Error())
		raygun.CreateError(err.Error())
		http.Error(w, err.Error(), 500)
		return BaseData{error: err}
	}

	return BaseData{
		Settings: settings,
		Board:    board,
		Lists:    lists,
		Prefs:    prefs,
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
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			// this error doesn't matter, since in the majority of cases there will be no standalone page here anyway.
			return card, err
		} else {
			// unknown error. report to raygun and proceed as if nothing was found
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			return card, err
		}
	}
	card.IsPage = true
	return card, nil
}

func index(w http.ResponseWriter, r *http.Request) {
	countPageViews()
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// pagination
	context.Page = 1
	context.HasPrev = false
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil || page < 0 {
			log.Print(err.Error())
			log.Print(val + " is not a page number.")
			raygun.CreateError(err.Error())
			page = 1
		}
		context.Page = page
		if context.Page > 1 {
			context.HasPrev = true
		}
	}
	// ~

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
  AND lists.visible
  AND cards.visible
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
	countPageViews()
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// pagination
	context.Page = 1
	context.HasPrev = false
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil || page < 0 {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			page = 1
		}
		context.Page = page
		if context.Page > 1 {
			context.HasPrev = true
		}
	}
	// ~

	ppp := context.Prefs.PostsPerPage()
	listSlug := mux.Vars(r)["list-slug"]

	// fetch home cards for this list
	var cards []Card
	err = db.Select(&cards, `
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
  ORDER BY pos
  OFFSET $3
  LIMIT $4
)
ORDER BY pos
    `, context.Board.Id, listSlug, ppp*(context.Page-1), ppp+1)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			// don't report to raygun, we already know the error and it doesn't matter
			http.Error(w, "there is not a list here.", 404)
			return
		} else {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
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

	context.Aggregator = list
	context.Cards = cards

	fmt.Fprint(w,
		mustache.RenderFileInLayout("templates/list.html",
			"templates/base.html",
			context),
	)
}

func label(w http.ResponseWriter, r *http.Request) {
	countPageViews()
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// pagination
	context.Page = 1
	context.HasPrev = false
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil || page < 0 {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			page = 1
		}
		context.Page = page
		if context.Page > 1 {
			context.HasPrev = true
		}
	}
	// ~

	ppp := context.Prefs.PostsPerPage()
	labelSlug := mux.Vars(r)["label-slug"]

	// fetch home cards for this label
	var cards []Card
	err = db.Select(&cards, `
(
  SELECT slug,
         name,
         null AS due,
         id,
         0 AS pos,
         '' AS cover
  FROM labels
  WHERE board_id = $1
    AND slug = $2
) UNION ALL (
  SELECT cards.slug,
         cards.name,
         cards.due,
         cards.id,
         cards.pos,
         coalesce(cards.cover, '') AS cover
  FROM cards
  INNER JOIN labels
  ON labels.id = ANY(cards.labels)
  WHERE board_id = $1
    AND (labels.slug = $2 OR labels.id = $2)
    AND cards.visible
  ORDER BY pos
  OFFSET $3
  LIMIT $4
)
ORDER BY pos
    `, context.Board.Id, labelSlug, ppp*(context.Page-1), ppp+1)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			// don't report to raygun, we already know the error and it doesn't matter
			http.Error(w, "there is not a label here.", 404)
			return
		} else {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// the first row is a Label dressed as a Card
	label := Label{
		Name:  cards[0].Name,
		Color: cards[0].Color,
		Slug:  cards[0].Slug,
	}
	cards = cards[1:]

	if len(cards) > ppp {
		context.HasNext = true
		cards = cards[:ppp]
	} else {
		context.HasNext = false
	}

	context.Aggregator = label
	context.Cards = cards

	fmt.Fprint(w,
		mustache.RenderFileInLayout("templates/list.html",
			"templates/base.html",
			context),
	)
}

func cardRedirect(w http.ResponseWriter, r *http.Request) {
	identifier := mux.Vars(r)["card-id-or-shortLink"]
	kind := "id"
	if len(identifier) < 15 {
		kind = "shortLink"
	}

	var slugs []string
	err := db.Select(&slugs, fmt.Sprintf(`
WITH card AS (
  SELECT list_id, slug
  FROM cards
  WHERE "%s" = $1
)
SELECT slug
FROM (
    (SELECT slug, 1 AS listfirst FROM card)
  UNION
    (SELECT lists.slug AS slug, 0 AS listfirst
    FROM lists
    INNER JOIN card ON list_id = id)
)y
ORDER BY listfirst
    `, kind), identifier)
	if err != nil {
		log.Print(err)
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
		log.Print(err)
		http.Error(w, "there is not a list here.", 404)
		return
	}

	http.Redirect(w, r, "/"+slug+"/", 302)
}

func card(w http.ResponseWriter, r *http.Request) {
	countPageViews()
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
SELECT slug, name, due, id, "desc", attachments, checklists, labels, cover
FROM (
  (
    SELECT slug,
           name,
           null AS due,
           id,
           '' AS "desc",
           '""'::jsonb AS attachments,
           '""'::jsonb AS checklists,
           '""'::json AS labels,
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
           array_to_json(array(SELECT row_to_json(l) FROM labels AS l WHERE l.id = ANY(cards.labels))) AS labels,
           1 AS sort,
           coalesce(cards.cover, '') AS cover
    FROM cards
    INNER JOIN lists
    ON lists.id = cards.list_id
    WHERE cards.slug = $3
      AND lists.slug = $2
      AND cards.visible
    GROUP BY cards.id
  )
) AS u
ORDER BY sort
	`, context.Board.Id, listSlug, cardSlug)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			// don't report to raygun, we already know the error and it doesn't matter
			http.Error(w, "there is not a card here.", 404)
			return
		} else {
			raygun.CreateError(err.Error())
			log.Print(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// the first row is a List dressed as a Card
	list := List{
		Name: cards[0].Name,
		Slug: cards[0].Slug,
	}
	context.Aggregator = list
	context.Card = cards[1]

	fmt.Fprint(w,
		mustache.RenderFileInLayout("templates/card.html",
			"templates/base.html",
			context),
	)
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
			http.Error(w, "there is not a card here.", 404)
		} else {
			log.Print(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
		}
		return
	}
	fmt.Fprint(w, desc)
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
	db.SetMaxOpenConns(7)

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
		// try to return a standalone page
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			card, err := getPageAt(r.URL.Path)
			if err != nil {
				next.ServeHTTP(w, r)
			} else {
				countPageViews()
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

	// router
	router := mux.NewRouter()
	router.StrictSlash(true) // redirects '/path' to '/path/'
	middle.UseHandler(router)

	// > static
	router.HandleFunc("/favicon.ico", favicon)
	router.HandleFunc("/robots.txt", httpError(404))

	// > redirect from permalinks
	router.HandleFunc("/c/{card-id-or-shortLink}/", cardRedirect)
	router.HandleFunc("/l/{list-id}/", listRedirect)

	// > helpers
	router.HandleFunc("/c/{card-id-or-shortLink}/desc", cardDesc)

	// > normal pages and index
	router.HandleFunc("/p/{page:[0-9]+}/", index)
	router.HandleFunc("/tag/{label-slug}/", label)
	router.HandleFunc("/{list-slug}/p/{page:[0-9]+}/", list)
	router.HandleFunc("/{list-slug}/{card-slug}/", card)
	router.HandleFunc("/{list-slug}/", list)
	router.HandleFunc("/", index)

	// > errors
	router.NotFoundHandler = http.HandlerFunc(httpError(404))
	// ~

	log.Print(":: SITES :: listening at port " + settings.Port)
	http.ListenAndServe(":"+settings.Port, middle)
}
