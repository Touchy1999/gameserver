import uuid
from enum import IntEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    # UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
    # サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
    # ユーザーによるリトライは一般的には良くないけれども、確率が非常に低ければ許容できる場合もある。
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print(f"create_user(): {result.lastrowid=}")  # DB側で生成されたPRIMARY KEYを参照できる
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken("Invalid token")

        # Now, update the user's information
        conn.execute(
            text(
                "UPDATE `user` SET `name` = :name, `leader_card_id` = :leader_card_id "
                "WHERE `token` = :token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )

        print("User information updated successfully")


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    OK = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, host_id) VALUES (:live_id, :host_id)"
            ),
            {"live_id": live_id, "host_id": user.id},
        )

        room_id = result.lastrowid
       
        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, member_id, diff) VALUES (:room_id, :member_id, :diff)"
            ),
            {"room_id": room_id, "member_id": user.id, "diff": difficulty},
        )

        print(f"Room created with ID: {room_id}")

        return room_id


def get_rooms_by_live_id(live_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, (SELECT COUNT(*) FROM `room_member` WHERE `room_member`.`room_id` = `room`.`room_id` AND `room`.`live_id` = :live_id) AS `joined_user_count`, `capacity` AS `max_user_count` FROM `room` WHERE `live_id` = :live_id"
            ),
            {"live_id": live_id},
        )
        rooms = result.fetchall()
        room_list = [
            {
                "room_id": room[0],
                "live_id": room[1],
                "joined_user_count": room[2],
                "max_user_count": room[3],
            }
            for room in rooms
        ]

        return room_list


def get_result_by_room_id(token: str, room_id: int, difficulty: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        result = conn.execute(
            text(
                "SELECT `capacity`, `waiting_status`, (SELECT COUNT(*) FROM `room_member` WHERE `room_member`.`room_id` = `room`.`room_id` AND `room`.`room_id` = :room_id) AS `joined_user_count` FROM `room` WHERE `room_id` = :room_id"
            ),
            {"room_id": room_id},
        )
        room_data = result.fetchone()

        if room_data is not None and room_data[1] != 3 and room_data[0] is not None and room_data[0] > room_data[2]:
            # 条件が満たされている場合、room_member テーブルに挿入を行う
            with engine.begin() as conn2:
                conn2.execute(
                    text(
                        "INSERT INTO `room_member` (`room_id`, `member_id`, `diff`) VALUES (:room_id, :member_id, :diff)"
                    ),
                    {"room_id": room_id, "member_id": user.id, "diff": difficulty},
                )

            room_status = {
                "max_user_count": room_data[0],
                "waiting_status": room_data[1],
                "joined_user_count": room_data[2],
            }
        else:
            room_status = None
        return room_status


def get_users_in_room(token: str, room_id: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        result = conn.execute(
            text(
                "SELECT `room_member`.`member_id`, `user`.`name`, `user`.`leader_card_id`, `room_member`.`diff`, `room`.`host_id` FROM `user`, `room_member`, `room` WHERE `user`.`id` = `room_member`.`member_id` AND `room`.`room_id` = `room_member`.`room_id` AND `room`.`room_id` = :room_id"
            ),
            {"room_id": room_id},
        )
        users = result.fetchall()
        user_list = [
            {
                "user_id": user_1[0],
                "name": user_1[1],
                "leader_card_id": user_1[2],
                "select_difficulty": user_1[3],
                "is_me": user.id == user_1[0],
                "is_host": user.id == user_1[4],
            }
            for user_1 in users
        ]

        result2 = conn.execute(
            text(
                "SELECT `waiting_status` FROM `room` WHERE `room_id` = :room_id"
            ),
            {"room_id": room_id},
        )
        room_status = result2.fetchone()
        if room_status is not None:
            wait_status = room_status[0]
        else:
            wait_status = None

        return wait_status, user_list


def start_live_in_room(token: str, room_id: int):
    with engine.begin() as conn:
        conn.execute(
                text(
                    "UPDATE `room` SET `waiting_status` = 2 WHERE `room_id` = :room_id"
                ),
                {"room_id": room_id},
        )


def leave_room(token: str, room_id: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        conn.execute(
                text(
                    "DELETE FROM `room_member` WHERE `room_id` = :room_id AND `member_id` = :user_id"
                ),
                {"room_id": room_id, "user_id": user.id},
        )


def room_end(token: str, room_id: int, judge_count_list: list[int], score: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        conn.execute(
                text(
                    "UPDATE `user` SET `score_sum` = `score_sum` + :score WHERE `id` = :user_id"
                ),
                {"score": score, "user_id": user.id},
        )

        conn.execute(
                text(
                    "UPDATE `room_member` SET `perfect` = :perfect, `great` =:great, `good` = :good, `bad` = :bad, `miss` = :miss WHERE `room_id` = :room_id AND `id` = :user_id"
                ),
                {"room_id": room_id, "score": score, "user_id": user.id, "perefct": judge_count_list[0], "great": judge_count_list[1], "good": judge_count_list[2], "bad": judge_count_list[3], "miss": judge_count_list[4]},
        )


def room_result(token: str, room_id: int):
    with engine.begin() as conn:
        # user = _get_user_by_token(conn, token)
        conn.execute(
                    text(
                        "UPDATE `room` SET `waiting_status` = 3 WHERE room_id = :room_id"
                    ),
                    {"room_id": room_id},
        )

        result = conn.execute(
                    text(
                        "SELECT `member_id`, `perfect`, `great`, `good`, `bad`, `miss`, `score` FROM `room_member` WHERE room_id = :room_id"
                    ),
                    {"room_id": room_id},
        )

        users = result.fetchall()
        user_list = [
            {
                "user_id": user_1[0],
                "judge_count_list": [user_1[1], user_1[2], user_1[3], user_1[4], user_1[5]],
                "score": user_1[6],
            }
            for user_1 in users
        ]
        return user_list
