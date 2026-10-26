import unittest

from bot.links import MessageLink, build_message_url, parse_message_link


class ParseMessageLinkTest(unittest.TestCase):
    def test_private_chat(self):
        self.assertEqual(
            parse_message_link("https://t.me/c/1234567890/42"),
            MessageLink(chat=-1001234567890, message_id=42),
        )

    def test_public_chat(self):
        self.assertEqual(
            parse_message_link("https://t.me/some_chat/7"),
            MessageLink(chat="@some_chat", message_id=7),
        )

    def test_topic_forms_use_last_segment(self):
        self.assertEqual(
            parse_message_link("https://t.me/c/1234567890/5/42"),
            MessageLink(chat=-1001234567890, message_id=42),
        )
        self.assertEqual(
            parse_message_link("t.me/some_chat/5/42"),
            MessageLink(chat="@some_chat", message_id=42),
        )

    def test_harmless_query_and_whitespace(self):
        self.assertEqual(
            parse_message_link("  https://t.me/c/123/9?single \n"),
            MessageLink(chat=-100123, message_id=9),
        )
        self.assertEqual(
            parse_message_link("https://t.me/c/123/9?thread=4"),
            MessageLink(chat=-100123, message_id=9),
        )

    def test_rejects_non_links(self):
        for text in [
            "",
            "hello",
            "look at https://t.me/c/123/9",
            "https://example.com/c/123/9",
            "https://t.me/some_chat",  # a chat, not a message
            "https://t.me/c/123",
            "https://t.me/c/abc/9",
            "https://t.me/c/123/0",
            "https://t.me/joinchat/9",
            "https://t.me/s/some_chat/9",
            "https://t.me/ab/9",  # username too short
            "https://t.me/some_chat/9?comment=3",
        ]:
            with self.subTest(text=text):
                self.assertIsNone(parse_message_link(text))


class BuildMessageUrlTest(unittest.TestCase):
    def test_username_wins(self):
        self.assertEqual(
            build_message_url(-1001234567890, "some_chat", 5),
            "https://t.me/some_chat/5",
        )

    def test_private_supergroup(self):
        self.assertEqual(
            build_message_url(-1001234567890, None, 5), "https://t.me/c/1234567890/5"
        )

    def test_basic_group_has_no_link(self):
        self.assertIsNone(build_message_url(-4567, None, 5))


if __name__ == "__main__":
    unittest.main()
