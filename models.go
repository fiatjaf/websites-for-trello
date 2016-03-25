package main

import (
	"bytes"
	"encoding/json"
	"regexp"
	"strconv"
	"strings"
	"time"

	log "github.com/Sirupsen/logrus"
	"github.com/jmoiron/sqlx/types"
	"github.com/shurcooL/go/github_flavored_markdown"
)

const CARDLINKMATCHEREXPRESSION = "\\]\\(https?://trello.com/c/([^/]+)(/[\\w-]*)?\\)"
const URLARRAYSTRINGSEPARATOR = "|,|"

var CardLinkMatcher *regexp.Regexp

func renderMarkdown(md string) string {
	mdBytes := []byte(md)
	mdBytes = CardLinkMatcher.ReplaceAllFunc(mdBytes, func(match []byte) []byte {
		shortLink := append(CardLinkMatcher.FindSubmatch(match)[1], ")"...)
		return append([]byte("](/c/"), shortLink...)
	})
	html := github_flavored_markdown.Markdown(mdBytes)
	return string(html)
}

type SearchResults []Card

func (o SearchResults) Some() bool {
	if len(o) > 0 {
		return true
	}
	return false
}

func (o SearchResults) Len() int {
	return len(o)
}

type Link struct {
	Text string
	Url  string
}

type Board struct {
	Id   string
	Name string
	Desc string
}

type User struct {
	Id       string `db:"_id" json:"_id"`
	Username string `db:"id" json:"id"`
}

func (o Board) DescRender() string {
	return renderMarkdown(o.Desc)
}

type Aggregator interface {
	Test() interface{}
}

type List struct {
	Id   string
	Name string
	Slug string
	Pos  int
}

type Label struct {
	Id    string
	Name  string
	Slug  string
	Color string
}

func (o Label) NameOrSpaces() string {
	if o.Name == "" {
		return "       "
	}
	return o.Name
}

func (o Label) SlugOrId() string {
	if o.Slug == "" {
		return o.Id
	}
	return o.Slug
}

type Card struct {
	Id          string
	ShortLink   string `db:"shortLink"`
	Name        string
	PageTitle   string `db:"pageTitle"`
	Slug        string
	Cover       string
	Desc        string
	Excerpt     string
	Due         interface{}
	Comments    []Comment
	List_id     string
	Users       types.JsonText
	Labels      types.JsonText
	Checklists  types.JsonText
	Attachments types.JsonText
	Syndicated  string // string of |,|-separated URLs, "https://twitter.com/21a|,|https://facebook.com/234"
	IsPage      bool
	Color       string // THIS IS JUST FOR DISGUISING LABELS AS CARDS
}

func (card Card) DescRender() string {
	return renderMarkdown(card.Desc)
}

func (card Card) HasExcerpt() bool {
	if strings.TrimSpace(card.Excerpt) == "" {
		return false
	}
	return true
}

func (card Card) HasCover() bool {
	if card.Cover != "" {
		/* cover must be in the attachments array */
		for _, attachment := range card.GetAttachments() {
			if attachment.Url == card.Cover {
				return true
			}
		}
	}

	return false
}

func (card Card) GetChecklists() []Checklist {
	var checklists []Checklist
	if !bytes.Equal(card.Checklists, nil) {
		err := json.Unmarshal(card.Checklists, &checklists)
		if err != nil {
			log.WithFields(log.Fields{
				"err":  err.Error(),
				"json": string(card.Checklists[:]),
			}).Warn("Problem unmarshaling checklists JSON")
		}
	}
	visibleChecklists := checklists[:0]
	for _, c := range checklists {
		if !strings.HasPrefix(c.Name, "_") {
			visibleChecklists = append(visibleChecklists, c)
		}
	}
	return visibleChecklists
}

func (card Card) GetAttachments() []Attachment {
	var attachments []Attachment
	if !bytes.Equal(card.Attachments, nil) {
		err := json.Unmarshal(card.Attachments, &attachments)
		if err != nil {
			log.WithFields(log.Fields{
				"err":  err.Error(),
				"json": string(card.Attachments[:]),
			}).Warn("Problem unmarshaling attachments JSON")
		}
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

func (card Card) GetAuthors() []User {
	var users []User
	if !bytes.Equal(card.Users, nil) {
		err := json.Unmarshal(card.Users, &users)
		if err != nil {
			log.WithFields(log.Fields{
				"err":  err.Error(),
				"json": string(card.Users[:]),
			}).Warn("Problem unmarshaling authors JSON")
		}
	}
	return users
}

func (card Card) AuthorHTML() string {
	users := card.GetAuthors()

	if len(users) == 0 {
		return ""
	} else if len(users) == 1 {
		return `<address><a rel="author" target="_blank" href="https://trello.com/` + users[0].Id + `">` + users[0].Username + `</a></address>`
	} else if len(users) == 2 {
		return `<address><a rel="author" target="_blank" href="https://trello.com/` + users[0].Id + `">` + users[0].Username + `</a> & <a href="https://trello.com/` + users[1].Id + `" "target="_blank">` + users[1].Username + `</a></address>`
	} else {
		return `<address><a rel="author" target="_blank" href="https://trello.com/` + users[0].Id + `">` + users[0].Username + `</a> et al.</address>`
	}
}

func (card Card) GetLabels() []Label {
	var labels []Label
	if !bytes.Equal(card.Labels, nil) {
		err := json.Unmarshal(card.Labels, &labels)
		if err != nil {
			log.WithFields(log.Fields{
				"err":  err.Error(),
				"json": string(card.Labels[:]),
			}).Warn("Problem unmarshaling labels JSON")
		}
	}
	return labels
}

func (card Card) SyndicationTargets() []string {
	return strings.Split(card.Syndicated, URLARRAYSTRINGSEPARATOR)
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

type Comment struct {
	Id            string
	AuthorName    string `db:"author_name"`
	AuthorURL     string `db:"author_url"`
	Body          string
	SourceDisplay string `db:"source_display"`
	SourceURL     string `db:"source_url"`
}

func (comment Comment) BodyRender() string {
	return renderMarkdown(comment.Body)
}

/* mustache helpers */
func (comment Comment) Date() time.Time {
	unix, err := strconv.ParseInt(comment.Id[:8], 16, 0)
	if err != nil {
		return time.Now()
	}
	return time.Unix(unix, 0)
}

func (comment Comment) PrettyDate() string {
	date := comment.Date()
	return date.Format("2 Jan 2006")
}

func (comment Comment) IsoDate() string {
	date := comment.Date()
	return date.Format("2006-01-02T15:04:05.999")
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

func (o Label) Test() interface{} {
	if o.Slug != "" {
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
