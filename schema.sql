use webapp;

DROP TABLE IF EXISTS `user`;
DROP TABLE IF EXISTS `room`;
DROP TABLE IF EXISTS `room_member`;

CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

CREATE TABLE `room` (
  `room_id` int NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `host_id` bigint DEFAULT NULL,
  `diff` int DEFAULT NULL,
  PRIMARY KEY (`room_id`),
  FOREIGN KEY (`host_id`) REFERENCES `user`(`id`),
);

CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `member_id` bigint NOT NULL,
  PRIMARY KEY (`room_id`, `member_id`),
  FOREIGN KEY (`room_id`) REFERENCES `room`(`room_id`),
  FOREIGN KEY (`member_id`) REFERENCES `user`(`id`)
);