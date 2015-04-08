package main

import (
	"strings"
	"time"
)

type BaseData struct {
	Board    Board
	Lists    []List
	List     List
	Author   Author
	Cards    []Card
	Card     Card
	HasNext  bool
	HasPrev  bool
	Prefs    Preferences
	Settings Settings
}

type Preferences struct {
	Favicon      string
	Domain       string
	includes     string
	postsPerPage string `json:"posts-per-page"`
}

func (prefs Preferences) JS() []string {
	includes := strings.Split(strings.ToLower(prefs.includes), ",")
	js := make([]string, 0)
	for _, incl := range includes {
		if strings.HasSuffix(incl, ".js") {
			js = append(js, incl)
		}
	}
	return js
}

func (prefs Preferences) CSS() []string {
	includes := strings.Split(strings.ToLower(prefs.includes), ",")
	css := make([]string, 0)
	for _, incl := range includes {
		if strings.HasSuffix(incl, ".css") {
			css = append(css, incl)
		}
	}
	return css
}

type Board struct {
	Id   interface{}
	Name string
	Desc string
}

type Author struct {
	Id           interface{}
	Bio          string
	AvatarHash   interface{}
	GravatarHash interface{}
}

type List struct {
	Id   interface{}
	Name string
	Slug string
	Pos  int
}

type Card struct {
	Id         interface{}
	Name       string
	Slug       string
	Desc       string
	Due        interface{}
	Created_on time.Time
	List_id    string
	/* temporary */
	URL string
}

func (card Card) Url(list List) string {
	if list.Id == nil {
		return "/from_list/" + card.List_id + "/" + card.Slug
	}
	return "/" + list.Slug + "/" + card.Slug
}

func (card Card) Date() time.Time {
	if card.Due != nil {
		return card.Due.(time.Time)
	} else {
		return card.Created_on
	}
}

func (card Card) PrettyDate() string {
	date := card.Date()
	return date.Format("2 Jan 2006")
}

func (card Card) IsoDate() string {
	date := card.Date()
	return date.Format("2006-01-02T15:04:05.999")
}

// mustache helpers
func (o Board) Test() interface{} {
	if o.Id != nil {
		return o
	}
	return false
}

func (o Author) Test() interface{} {
	if o.Id != nil {
		return o
	}
	return false
}

func (o List) Test() interface{} {
	if o.Id != nil {
		return o
	}
	return false
}

func (o Card) Test() interface{} {
	if o.Id != nil {
		return o
	}
	return false
}
