package main

import (
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/gorilla/context"
)

type key int

const k key = 23

func loadRequestData(r *http.Request) RequestData {
	if val := context.Get(r, k); val != nil {
		return val.(RequestData)
	}
	return RequestData{}
}

func saveRequestData(r *http.Request, requestData RequestData) {
	context.Set(r, k, requestData)
}

func clearContextMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		next.ServeHTTP(w, r)
		context.Clear(r) // clears after handling everything.
	})
}

type RequestData struct {
	error
	Aggregator       Aggregator
	Request          *http.Request
	Board            Board
	Lists            []List
	Cards            []Card
	Card             Card
	Page             int
	SearchQuery      string
	TypedSearchQuery bool
	SearchResults    SearchResults
	HasNext          bool
	HasPrev          bool
	Prefs            Preferences
	Settings         Settings
	ShowMF2          bool
	Content          string
}

func (b RequestData) NavItems() []Link {
	var lists []Link
	var navItems []Link
	for _, list := range b.Lists {
		lists = append(lists, Link{
			Text: list.Name,
			Url:  "/" + list.Slug + "/",
		})
	}
	for _, link := range b.Prefs.Nav {
		if link.Text == "__lists__" {
			navItems = append(navItems, lists...)
		} else {
			navItems = append(navItems, link)
		}
	}
	return navItems
}

func (b RequestData) NextPage() int {
	return b.Page + 1
}

func (b RequestData) PrevPage() int {
	return b.Page - 1
}

type Preferences struct {
	Header struct {
		Text  string
		Image string
	}
	Comments struct {
		Display     bool
		Box         bool
		Webmentions bool
	}
	Aside             string
	Favicon           string
	Domain            string
	Includes          []string
	Nav               []Link
	PostsPerPageValue string `json:"posts-per-page"`
	ExcerptsValue     string `json:"excerpts"`
}

func (prefs Preferences) HasHeaderImage() bool {
	if prefs.Header.Image != "" {
		return true
	}
	return false
}

func (prefs Preferences) JS() []string {
	js := make([]string, 0)
	for _, incl := range prefs.Includes {
		u, err := url.Parse(incl)
		if err != nil {
			continue
		}
		if strings.HasSuffix(u.Path, ".js") {
			js = append(js, incl)
		}
	}
	return js
}

func (prefs Preferences) CSS() []string {
	css := make([]string, 0)
	for _, incl := range prefs.Includes {
		u, err := url.Parse(incl)
		if err != nil {
			continue
		}
		if strings.HasSuffix(u.Path, ".css") {
			css = append(css, incl)
		}
	}
	return css
}

func (prefs Preferences) PostsPerPage() int {
	ppp, err := strconv.Atoi(prefs.PostsPerPageValue)
	if err != nil {
		return 7
	}
	if ppp > 15 {
		return 15
	}
	return ppp
}

func (prefs Preferences) Excerpts() int {
	limit, err := strconv.Atoi(prefs.ExcerptsValue)
	if err != nil {
		return 0
	}
	if limit > 300 {
		return 300
	}
	return limit
}

func (prefs Preferences) ShowExcerpts() bool {
	if prefs.Excerpts() > 0 {
		return true
	}
	return false
}
