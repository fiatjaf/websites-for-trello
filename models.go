package main

import (
	"github.com/jmoiron/sqlx/types"
	"github.com/mitchellh/mapstructure"
	"github.com/shurcooL/go/github_flavored_markdown"
	"log"
	"net/url"
	"strconv"
	"strings"
	"time"
)

func renderMarkdown(md string) string {
	html := github_flavored_markdown.Markdown([]byte(md))
	return string(html[:])
}

type BaseData struct {
	error
	Board    Board
	Lists    []List
	List     List
	Cards    []Card
	Card     Card
	Page     int
	HasNext  bool
	HasPrev  bool
	Prefs    Preferences
	Settings Settings
}

func (b BaseData) NavItems() []Link {
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

func (b BaseData) NextPage() int {
	return b.Page + 1
}

func (b BaseData) PrevPage() int {
	return b.Page - 1
}

type Preferences struct {
	Favicon      string
	Domain       string
	Includes     []string
	Nav          []Link
	postsPerPage string `json:"posts-per-page"`
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
	ppp, err := strconv.Atoi(prefs.postsPerPage)
	if err != nil {
		return 7
	}
	return ppp
}

type Link struct {
	Text string
	Url  string
}

type Board struct {
	Id   interface{}
	Name string
	Desc string

	/* mix with user */
	User_id      string
	Bio          string
	AvatarHash   interface{} `db:"avatarHash"`
	GravatarHash interface{} `db:"gravatarHash"`
}

func (o Board) DescRender() string {
	return renderMarkdown(o.Desc)
}

func (o Board) BioRender() string {
	return renderMarkdown(o.Bio)
}

func (o Board) GetAvatar() interface{} {
	if o.AvatarHash != nil {
		return "//trello-avatars.s3.amazonaws.com/" + string(o.AvatarHash.([]uint8)) + "/170.png"
	} else if o.GravatarHash != nil {
		return "//gravatar.com/avatar/" + string(o.GravatarHash.([]uint8))
	}
	return nil
}

func (o Board) HasUser() bool {
	if o.User_id != "" {
		return true
	}
	return false
}

func (o Board) UserHasBio() bool {
	if o.Bio != "" {
		return true
	}
	return false
}

type List struct {
	Id   string
	Name string
	Slug string
	Pos  int
}

type Card struct {
	Id          string
	Name        string
	PageTitle   string `db:"pageTitle"`
	Slug        string
	Cover       string
	Desc        string
	Due         interface{}
	List_id     string
	Labels      []interface{}
	Checklists  types.JsonText
	Attachments types.JsonText
	IsPage      bool
}

func (card Card) DescRender() string {
	return renderMarkdown(card.Desc)
}

func (card Card) HasCover() bool {
	if card.Cover == "" {
		return false
	}
	return true
}

func (card Card) Date() time.Time {
	if card.Due != nil {
		return card.Due.(time.Time)
	} else {
		unix, err := strconv.ParseInt(card.Id[:8], 16, 0)
		if err != nil {
			return time.Now()
		}
		return time.Unix(unix, 0)
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

func (card Card) GetChecklists() []Checklist {
	var dat map[string]interface{}
	err := card.Checklists.Unmarshal(&dat)
	if err != nil {
		log.Print("Problem unmarshaling checklists JSON")
		log.Print(err)
	}
	var checklists []Checklist
	err = mapstructure.Decode(dat["checklists"], &checklists)
	if err != nil {
		log.Print("Problem converting checklists map to struct")
		log.Print(err)
	}
	return checklists
}

func (card Card) GetAttachments() []Attachment {
	var dat map[string]interface{}
	err := card.Attachments.Unmarshal(&dat)
	if err != nil {
		log.Print("Problem unmarshaling attachments JSON")
		log.Print(err)
	}
	var attachments []Attachment
	err = mapstructure.Decode(dat["attachments"], &attachments)
	if err != nil {
		log.Print("Problem converting attachments map to struct")
		log.Print(err)
	}
	return attachments
}

func (card Card) HasAttachments() bool {
	attachments := card.GetAttachments()
	if len(attachments) > 0 {
		return true
	}
	return false
}

type Checklist struct {
	Name       string
	CheckItems []CheckItem
}

type CheckItem struct {
	State string
	Name  string
}

func (c CheckItem) Complete() bool {
	return c.State == "complete"
}
func (o CheckItem) NameRender() string {
	return renderMarkdown(o.Name)
}

type Attachment struct {
	Name      string
	Url       string
	EdgeColor string
}

// mustache helpers
func (o Board) Test() interface{} {
	if o.Id != nil {
		return o
	}
	return false
}

func (o List) Test() interface{} {
	if o.Slug != "" {
		return o
	}
	return false
}

func (o Card) Test() interface{} {
	if o.Slug != "" {
		return o
	}
	return false
}
