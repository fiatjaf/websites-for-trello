
userRequired = (r, w, next) ->
  console.log r.session
  if not r.session.userid
    return w.sendStatus 401
  next()

module.exports =
  userRequired: userRequired
