package main

import (
	"fmt"
	"log"
	"net/http"
	"strconv"

	"github.com/MindscapeHQ/raygun4go"
	"github.com/gorilla/mux"
)

func index(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	countPageViews(requestData)
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// pagination
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil || page < 0 {
			log.Print(err.Error())
			log.Print(val + " is not a page number.")
			raygun.CreateError(err.Error())
			page = 1
		}
		requestData.Page = page
		if requestData.Page > 1 {
			requestData.HasPrev = true
		}
	}
	// ~

	// fetch cards for home
	err = completeWithIndexCards(&requestData)
	if err != nil {
		raygun.CreateError(err.Error())
		http.Error(w, err.Error(), 500)
		return
	}

	fmt.Fprint(w,
		renderOnTopOf(requestData,
			"templates/list.html",
			"templates/base.html",
		),
	)
}

func label(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	countPageViews(requestData)
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// pagination
	requestData.Page = 1
	requestData.HasPrev = false
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil || page < 0 {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			page = 1
		}
		requestData.Page = page
		if requestData.Page > 1 {
			requestData.HasPrev = true
		}
	}
	// ~

	ppp := requestData.Prefs.PostsPerPage()
	labelSlug := mux.Vars(r)["label-slug"]

	// fetch home cards for this label
	var cards []Card
	err = db.Select(&cards, `
(
  SELECT slug,
         name,
         '' AS excerpt,
         null AS due,
         id,
         '""'::json AS users,
         0 AS pos,
         '' AS cover,
         '""'::jsonb AS attachments
  FROM labels
  WHERE board_id = $2
    AND slug = $3
    AND visible
) UNION ALL (
  SELECT cards.slug,
         cards.name,
         substring(cards.desc from 0 for $1) AS excerpt,
         cards.due,
         cards.id,
         array_to_json(array(SELECT row_to_json(u) FROM users AS u WHERE u._id = ANY(cards.users))) AS users,
         cards.pos,
         coalesce(cards.cover, '') AS cover,
         cards.attachments->'attachments' AS attachments
  FROM cards
  INNER JOIN labels
  ON labels.id = ANY(cards.labels)
  WHERE board_id = $2
    AND (labels.slug = $3 OR labels.id = $3)
    AND cards.visible
    AND labels.visible
  ORDER BY pos
  OFFSET $4
  LIMIT $5
)
ORDER BY pos
    `, requestData.Prefs.Excerpts(), requestData.Board.Id, labelSlug, ppp*(requestData.Page-1), ppp+1)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			// don't report to raygun, we already know the error and it doesn't matter
			log.Print("label not found.")
			error404(w, r)
			return
		} else {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// we haven't found the requested label (when the label has 0 cards, we should get 1 here)
	if len(cards) < 1 {
		error404(w, r)
		return
	}

	// the first row is a Label dressed as a Card
	label := Label{
		Name:  cards[0].Name,
		Color: cards[0].Color,
		Slug:  cards[0].Slug,
	}
	cards = cards[1:]

	if len(cards) > ppp {
		requestData.HasNext = true
		cards = cards[:ppp]
	} else {
		requestData.HasNext = false
	}

	requestData.Aggregator = label
	requestData.Cards = cards

	fmt.Fprint(w,
		renderOnTopOf(requestData,
			"templates/list.html",
			"templates/base.html",
		),
	)
}

func card(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	countPageViews(requestData)
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
SELECT slug, name, due, id, "desc", attachments, checklists, labels, users, cover
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
           '""'::json AS users,
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
           cards.attachments->'attachments' AS attachments,
           cards.checklists->'checklists' AS checklists,
           array_to_json(array(SELECT row_to_json(l) FROM labels AS l WHERE l.id = ANY(cards.labels) AND l.visible)) AS labels,
           array_to_json(array(SELECT row_to_json(u) FROM users AS u WHERE u._id = ANY(cards.users))) AS users,
           1 AS sort,
           coalesce(cards.cover, '') AS cover
    FROM cards
    INNER JOIN lists
    ON lists.id = cards.list_id
    WHERE board_id = $1
      AND cards.slug = $3
      AND lists.slug = $2
      AND cards.visible
    GROUP BY cards.id
  )
) AS u
ORDER BY sort
	`, requestData.Board.Id, listSlug, cardSlug)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			// don't report to raygun, we already know the error and it doesn't matter
			log.Print("card not found.")
			error404(w, r)
			return
		} else {
			raygun.CreateError(err.Error())
			log.Print(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// we haven't found the requested list and card
	if len(cards) < 2 {
		error404(w, r)
		return
	}

	// the first row is a List dressed as a Card
	list := List{
		Name: cards[0].Name,
		Slug: cards[0].Slug,
	}
	requestData.Aggregator = list
	requestData.Card = cards[1]

	// comments
	if requestData.Prefs.Comments.Display && !requestData.Card.IsPage {
		var comments []Comment
		err = db.Select(&comments, `
SELECT id, author_url, author_name, body, source_display, source_url
FROM comments
WHERE card_id = $1
  AND body IS NOT NULL
ORDER BY id
    `, requestData.Card.Id)
		requestData.Card.Comments = comments
	}

	fmt.Fprint(w,
		renderOnTopOf(requestData,
			"templates/card.html",
			"templates/base.html",
		),
	)
}

func list(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	countPageViews(requestData)
	// raygun error reporting
	raygun, err := raygun4go.New("trellocms", settings.RaygunAPIKey)
	if err != nil {
		log.Print("unable to create Raygun client: ", err.Error())
	}
	raygun.Request(r)
	defer raygun.HandleError()
	// ~

	// pagination
	requestData.Page = 1
	requestData.HasPrev = false
	if val, ok := mux.Vars(r)["page"]; ok {
		page, err := strconv.Atoi(val)
		if err != nil || page < 0 {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			page = 1
		}
		requestData.Page = page
		if requestData.Page > 1 {
			requestData.HasPrev = true
		}
	}
	// ~

	ppp := requestData.Prefs.PostsPerPage()
	listSlug := mux.Vars(r)["list-slug"]

	// fetch home cards for this list
	var cards []Card
	err = db.Select(&cards, `
(
  SELECT slug,
         name,
         '' AS excerpt,
         null AS due,
         id,
         '""'::json AS labels,
         '""'::json AS users,
         0 AS pos,
         '' AS cover,
         '""'::jsonb AS attachments
  FROM lists
  WHERE board_id = $2
    AND slug = $3
    AND visible
) UNION ALL (
  SELECT cards.slug,
         cards.name,
         substring(cards.desc from 0 for $1) AS excerpt,
         cards.due,
         cards.id,
         array_to_json(array(SELECT row_to_json(l) FROM labels AS l WHERE l.id = ANY(cards.labels) AND l.visible)) AS labels,
         array_to_json(array(SELECT row_to_json(u) FROM users AS u WHERE u._id = ANY(cards.users))) AS users,
         cards.pos,
         coalesce(cards.cover, '') AS cover,
         cards.attachments->'attachments' AS attachments
  FROM cards
  INNER JOIN lists
  ON lists.id = cards.list_id
  WHERE board_id = $2
    AND lists.slug = $3
    AND lists.visible
    AND cards.visible
  ORDER BY pos
  OFFSET $4
  LIMIT $5
)
ORDER BY pos
    `, requestData.Prefs.Excerpts(), requestData.Board.Id, listSlug, ppp*(requestData.Page-1), ppp+1)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			// don't report to raygun, we already know the error and it doesn't matter
			log.Print("list not found.")
			error404(w, r)
			return
		} else {
			log.Print(err.Error())
			raygun.CreateError(err.Error())
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// we haven't found the requested list (when the list has 0 cards, we should get 1 here)
	if len(cards) < 1 {
		error404(w, r)
		return
	}

	// the first row is a List dressed as a Card
	list := List{
		Name: cards[0].Name,
		Slug: cards[0].Slug,
	}
	cards = cards[1:]

	if len(cards) > ppp {
		requestData.HasNext = true
		cards = cards[:ppp]
	} else {
		requestData.HasNext = false
	}

	requestData.Aggregator = list
	requestData.Cards = cards

	fmt.Fprint(w,
		renderOnTopOf(requestData,
			"templates/list.html",
			"templates/base.html",
		),
	)
}
