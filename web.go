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

	return BaseData{
		Settings: settings,
		Board:    board,
		Author:   author,
		Lists:    lists,
		Prefs:    prefs,
	}
}

func index(w http.ResponseWriter, r *http.Request) {
	context := getBaseData(r)
	response := mustache.RenderFileInLayout("templates/list.html",
		"templates/base.html",
		context)
	fmt.Fprint(w, response)
}

func main() {
	settings = LoadSettings()

	db, _ = sqlx.Connect("postgres", settings.DatabaseURL)
	db = db.Unsafe()

	router := mux.NewRouter()
	router.HandleFunc("/", index)

	http.Handle("/", router)

	port := os.Getenv("PORT")
	if port == "" {
		port = "5000"
	}
	log.Print("listening...")
	http.ListenAndServe(":"+port, nil)
}
