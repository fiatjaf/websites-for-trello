

userRequired = (r, w, next) ->
  if not r.session.user
    return w.sendStatus 401
  next()

module.exports =
  userRequired: userRequired
