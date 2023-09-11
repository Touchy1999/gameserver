import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import List
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


class ListRoomsRequest(BaseModel):
    live_id: int


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


class Room_info_list(BaseModel):
    room_info_list: list[RoomInfo]


class Join_room_result(BaseModel):
    join_room_result: JoinRoomResult


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


class RoomWait(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class Result_user_list(BaseModel):
    result_user_list: list[ResultUser]


class JoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomEnd(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty.value)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def list(request: ListRoomsRequest) -> Room_info_list:
    live_id = request.live_id
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

    return Room_info_list(room_info_list=room_info_list)


@app.post("/room/join")
def join(token: UserToken, req: JoinRequest) -> Join_room_result:
    room = model.get_result_by_room_id(token, req.room_id, req.select_difficulty)
    join_room_result = JoinRoomResult.OK
    if room is None:
        join_room_result = JoinRoomResult.OtherError

    # Check if the room is full
    elif room["joined_user_count"] >= room["max_user_count"]:
        join_room_result = JoinRoomResult.RoomFull

    # Check if the room is disbanded
    elif room["waiting_status"] == 3:
        join_room_result = JoinRoomResult.Disbanded

    return Join_room_result(join_room_result=join_room_result)


@app.post("/room/wait")
def wait(token: UserToken, req: RoomID) -> RoomWait:
    wait_status, user_list2 = model.get_users_in_room(token, req.room_id)
    room_user_list = [
        RoomUser(
            user_id=user_list["user_id"],
            name=user_list["name"],
            leader_card_id=user_list["leader_card_id"],
            select_difficulty=user_list["select_difficulty"],
            is_me=user_list["is_me"],
            is_host=user_list["is_host"],
        )
        for user_list in user_list2
    ]
    return RoomWait(status=wait_status, room_user_list=room_user_list)


@app.post("/room/start")
def start(token: UserToken, req: RoomID):
    model.start_live_in_room(token, req.room_id)
    return Empty()


@app.post("/room/leave")
def leave(token: UserToken, req: RoomID):
    model.leave_room(token, req.room_id)
    return Empty()


@app.post("/room/end")
def end(token: UserToken, req: RoomEnd) -> None:
    model.room_end(token, req.room_id, req.judge_count_list, req.score)
    return Empty()


@app.post("/room/result")
def result(token: UserToken, req: RoomID) -> Result_user_list:
    user_list = model.room_result(token, req.room_id)
    room_user_list = [
        ResultUser(
            user_id=user_list["user_id"],
            judge_count_list=user_list["judge_count_list"],
            score=user_list["score"],
        )
        for user_list in user_list
    ]
    return Result_user_list(result_user_list=room_user_list)


# @app.post("/room/start")
# def start_room(token: UserToken, req: RoomID):
#     """ルーム開始"""
#     print("/room/start", req)
#     model.start_room(token, req.room_id)
#     return Empty()
