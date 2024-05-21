from typing import cast

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

cache: dict[str, str] = {}

app = FastAPI()

proxy_url = "https://graph.qq.com"


@app.get("/oauth2.0/authorize")
async def authorize(request: Request):
    params = dict(request.query_params)

    res = httpx.get(proxy_url + request.url.path, params=params)

    return Response(
        content=res.content,
        status_code=res.status_code,
        headers=res.headers,
    )


@app.post("/oauth2.0/token")
async def post_token(request: Request):
    url = proxy_url + request.url.path
    req = dict(await request.form())
    req["fmt"] = "json"

    res = httpx.post(proxy_url + request.url.path, data=req)

    body = res.json()
    body["token_type"] = "Bearer"
    if body.get("error"):
        body["error"] = f"{body['error']} {body['error_description']}"
    else:
        cache[body["access_token"]] = cast(str, req["client_id"])
    return JSONResponse(
        status_code=res.status_code,
        content=body,
    )


@app.get("/oauth2.0/me")
async def me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header is required")
    token = auth_header.removeprefix("Bearer ")

    r0 = httpx.get(
        proxy_url + "/oauth2.0/me", params={"access_token": token, "fmt": "json"}
    )
    r0.raise_for_status()
    r0 = r0.json()
    openid = r0["openid"]

    client_id = cache.get(token)
    if not client_id:
        raise HTTPException(status_code=401, detail="Invalid access token")

    res = httpx.get(
        proxy_url + "/user/get_user_info",
        params={
            "access_token": token,
            "oauth_consumer_key": client_id,
            "openid": openid,
        },
    )
    body = res.json()

    body = {
        "sub": openid,
        "name": body["nickname"],
        "nickname": body["nickname"],
        "picture": body["figureurl_qq_2"],
        "avatar": body["figureurl_qq_2"],
        "provider": "qq",
        "gender": ({"男": "male", "女": "female"}).get(body["gender"], "unknown"),
    }

    return JSONResponse(
        status_code=res.status_code,
        content=body,
    )
