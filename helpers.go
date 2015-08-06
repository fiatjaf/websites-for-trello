package main

import (
	"encoding/json"
	"fmt"
	"github.com/MindscapeHQ/raygun4go"
	"github.com/jmoiron/sqlx/types"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
)

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
		Request:  r,
		Settings: settings,
		Board:    board,
		Lists:    lists,
		Prefs:    prefs,
		ShowMF2:  !strings.Contains(r.UserAgent(), "Mozilla"),
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

func filter(s []string, fn func(string) bool) []string {
	var p []string
	for _, v := range s {
		if fn(v) {
			p = append(p, v)
		}
	}
	return p
}

func search(query string, idBoard string) ([]Card, error) {
	var empty []Card

	// query trello
	qs := url.Values{}
	qs.Set("key", settings.TrelloBotAPIKey)
	qs.Set("token", settings.TrelloBotToken)
	qs.Set("modelTypes", "cards")
	qs.Set("idBoards", idBoard)
	qs.Set("cards_limit", "20")
	qs.Set("card_fields", "id,name")
	qs.Set("card_list", "true")
	qs.Set("query", query)

	res, err := http.Get("https://api.trello.com/1/search?" + qs.Encode())
	if err != nil {
		return empty, err
	}

	body, err := ioutil.ReadAll(res.Body)
	if err != nil {
		return empty, err
	}

	var result struct {
		Cards []struct {
			Id   string
			Name string
			List struct {
				Name string
			}
		}
	}
	err = json.Unmarshal(body, &result)
	if err != nil {
		return empty, err
	}

	// filter out cards starting with _ and lists starting with _
	var filteredcards []Card
	for _, c := range result.Cards {
		if !strings.HasPrefix(c.Name, "_") && !strings.HasPrefix(c.List.Name, "_") {
			filteredcards = append(filteredcards, Card{
				Id:   c.Id,
				Name: c.Name,
			})
		}
	}

	return filteredcards, nil
}
