import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import LiveDifficulty, JoinRoomResult, WaitRoomStatus

app = FastAPI()


# リクエストのvalidation errorをprintする
# このエラーが出たら、リクエストのModel定義が間違っている
@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(req, exc):
    print("Request validation error")
    print(f"{req.url=}\n{exc.body=}\n{exc=!s}")
    return await fastapi.exception_handlers.request_validation_exception_handler(
        req, exc
    )


# Sample API
@app.get("/")
async def root() -> dict:
    return {"message": "Hello World"}


# User APIs


# FastAPI 0.100 は model_validate_json() を使わないので、 strict モードにすると
# EnumがValidationエラーになってしまいます。
class UserCreateRequest(BaseModel):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


# Responseの方は strict モードを利用できます
class UserCreateResponse(BaseModel, strict=True):
    user_token: str


@app.post("/user/create")
def user_create(req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証動作確認用のサンプルAPI
# ゲームアプリは使わない
@app.get("/user/me")
def user_me(token: UserToken) -> model.SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update")
def update(req: UserCreateRequest, token: UserToken) -> Empty:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs


class RoomID(BaseModel):
    room_id: int


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def list(live_id: int) -> list[RoomInfo]:
    rooms = model.get_rooms_by_live_id(live_id)

    # Transform the fetched data into RoomInfo objects
    room_info_list = [
        RoomInfo(
            room_id=room["room_id"],
            live_id=room["live_id"],
            joined_user_count=room["joined_user_count"],
            max_user_count=room["max_user_count"],
        )
        for room in rooms
    ]

    return room_info_list


@app.post("/room/join")
def join(token: UserToken, room_id: int, select_difficulty: LiveDifficulty) -> JoinRoomResult:
    room = model.get_result_by_room_id(token, room_id, select_difficulty)
    if room is None:
        return JoinRoomResult.OtherError

    # Check if the room is full
    if room["joined_user_count"] >= room["max_user_count"]:
        return JoinRoomResult.RoomFull

    # Check if the room is disbanded
    if room["is_disbanded"]:
        return JoinRoomResult.Disbanded

    return JoinRoomResult.OK


# @app.post("/room/wait")
# def wait(room_id: int) -> tuple:
#     # Check if the room exists
#     room = model.get__by_live_id(room_id)
#     if room is None:
#         raise HTTPException(status_code=404, detail="Room not found")

#     # You can implement the logic to check the wait status of the room here
#     wait_status = model.get_room_wait_status(room_id)

#     # Fetch the list of users in the room
#     users = model.get_users_in_room(room_id)

#     # Transform the fetched user data into RoomUser objects
#     room_user_list = [
#         RoomUser(
#             user_id=user.user_id,
#             name=user.name,
#             leader_card_id=user.leader_card_id,
#             select_difficulty=user.select_difficulty,
#             is_me=False,  # You can set this based on your logic
#             is_host=user.is_host,  # Assuming you have a flag to identify the host
#         )
#         for user in users
#     ]

#     return wait_status, room_user_list

