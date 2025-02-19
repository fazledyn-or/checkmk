// Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the
// terms and conditions defined in the file COPYING, which is part of this
// source code package.

#include <memory>
#include <string_view>

#include "gtest/gtest.h"
#include "livestatus/strutil.h"

using namespace std::string_view_literals;

// next_token() tests ----------------------------------------------------------

TEST(StrutilTest, NextTokenEmptyText) {
    char text[] = "";
    char *current = text;

    char *token = next_token(&current, ';');

    EXPECT_EQ(current, text);
    EXPECT_EQ(token, nullptr);
}

TEST(StrutilTest, NextTokenDelimNotFound) {
    char text[] = "foo";
    char *current = text;

    char *token = next_token(&current, ';');

    EXPECT_EQ(current, text + "foo"sv.size());
    EXPECT_STREQ(current, "");
    EXPECT_STREQ(token, "foo");
}

TEST(StrutilTest, NextTokenEmptyToken) {
    char text[] = ";foo";
    char *current = text;

    char *token = next_token(&current, ';');

    EXPECT_EQ(current, text + 1);
    EXPECT_STREQ(current, "foo");
    EXPECT_STREQ(token, "");
}

TEST(StrutilTest, NextTokenDelimFoundAtEnd) {
    char text[] = "foo;";
    char *current = text;

    char *token = next_token(&current, ';');

    EXPECT_EQ(current, text + "foo"sv.size() + 1);
    EXPECT_STREQ(current, "");
    EXPECT_STREQ(token, "foo");
}

TEST(StrutilTest, NextTokenDelimFound) {
    char text[] = "foo;bar;baz";
    char *current = text;

    char *token = next_token(&current, ';');

    EXPECT_EQ(current, text + "foo"sv.size() + 1);
    EXPECT_STREQ(current, "bar;baz");
    EXPECT_STREQ(token, "foo");
}

// safe_next_token() tests -----------------------------------------------------

TEST(StrutilTest, SafeNextTokenNullptr) {
    char *current = nullptr;

    const char *token = safe_next_token(&current, ';');

    EXPECT_EQ(current, nullptr);
    EXPECT_STREQ(token, "");
}

TEST(StrutilTest, SafeNextTokenEmptyText) {
    char text[] = "";
    char *current = text;

    const char *token = safe_next_token(&current, ';');

    EXPECT_EQ(current, text);
    EXPECT_STREQ(token, "");
}

TEST(StrutilTest, SafeNextTokenDelimNotFound) {
    char text[] = "foo";
    char *current = text;

    const char *token = safe_next_token(&current, ';');

    EXPECT_EQ(current, text + "foo"sv.size());
    EXPECT_STREQ(current, "");
    EXPECT_STREQ(token, "foo");
}

TEST(StrutilTest, SafeNextTokenEmptyToken) {
    char text[] = ";foo";
    char *current = text;

    const char *token = safe_next_token(&current, ';');

    EXPECT_EQ(current, text + 1);
    EXPECT_STREQ(current, "foo");
    EXPECT_STREQ(token, "");
}

TEST(StrutilTest, SafeNextTokenDelimFoundAtEnd) {
    char text[] = "foo;";
    char *current = text;

    const char *token = safe_next_token(&current, ';');

    EXPECT_EQ(current, text + "foo"sv.size() + 1);
    EXPECT_STREQ(current, "");
    EXPECT_STREQ(token, "foo");
}

TEST(StrutilTest, SafeNextTokenDelimFound) {
    char text[] = "foo;bar;baz";
    char *current = text;

    const char *token = safe_next_token(&current, ';');

    EXPECT_EQ(current, text + "foo"sv.size() + 1);
    EXPECT_STREQ(current, "bar;baz");
    EXPECT_STREQ(token, "foo");
}

// next_field() tests ----------------------------------------------------------

TEST(StrutilTest, NextFieldEmptyText) {
    char text[] = "";
    char *current = text;

    char *token = next_field(&current);

    EXPECT_EQ(current, text);
    EXPECT_EQ(token, nullptr);
}

TEST(StrutilTest, NextFieldWhitespaceOnly) {
    char text[] = " \t\n ";
    char *current = text;

    char *token = next_field(&current);

    EXPECT_EQ(current, text + " \t\n "sv.size());
    EXPECT_STREQ(current, "");
    EXPECT_EQ(token, nullptr);
}

TEST(StrutilTest, NextFieldLeadingWhitespace) {
    char text[] = "  foo";
    char *current = text;

    char *token = next_field(&current);

    EXPECT_EQ(current, text + "  foo"sv.size());
    EXPECT_STREQ(current, "");
    EXPECT_STREQ(token, "foo");
}

TEST(StrutilTest, NextFieldTrailingWhitespace) {
    char text[] = "foo    ";
    char *current = text;

    char *token = next_field(&current);

    EXPECT_EQ(current, text + "foo"sv.size() + 1);
    EXPECT_STREQ(current, "   ");
    EXPECT_STREQ(token, "foo");
}

TEST(StrutilTest, NextFieldInnerWhitespace) {
    char text[] = "foo    bar";
    char *current = text;

    char *token = next_field(&current);

    EXPECT_EQ(current, text + "foo"sv.size() + 1);
    EXPECT_STREQ(current, "   bar");
    EXPECT_STREQ(token, "foo");
}
