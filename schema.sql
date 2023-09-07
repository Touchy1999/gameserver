use webapp;

DROP TABLE IF EXISTS `room_member`;
DROP TABLE IF EXISTS `room`;
DROP TABLE IF EXISTS `user`;


CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `host_id` bigint DEFAULT NULL,
  `capacity` int DEFAULT NULL, 
  `is_disbanded` boolean DEFAULT false,
  PRIMARY KEY (`room_id`),
  FOREIGN KEY (`host_id`) REFERENCES `user`(`id`)
);

CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `member_id` bigint NOT NULL,
  `diff` int DEFAULT 0,
  PRIMARY KEY (`room_id`, `member_id`),
  FOREIGN KEY (`room_id`) REFERENCES `room`(`room_id`),
  FOREIGN KEY (`member_id`) REFERENCES `user`(`id`)
);
