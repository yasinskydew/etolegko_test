"use client";

import {
  Box,
  Button,
  Field,
  Flex,
  Heading,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { getToken, setToken } from "@/lib/auth";
import { getErrorMessage, useLoginMutation } from "@/store/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [login, { isLoading }] = useLoginMutation();

  useEffect(() => {
    if (getToken()) router.replace("/companies");
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await login({ username, password }).unwrap();
      setToken(res.access_token);
      router.replace("/companies");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Flex minH="100vh" direction={{ base: "column", lg: "row" }}>
      <Flex
        display={{ base: "flex", lg: "flex" }}
        flex={{ base: "none", lg: "0 0 36%" }}
        bg="gray.900"
        color="white"
        p={{ base: "8", lg: "12" }}
        direction="column"
        justify="center"
        minH={{ base: "40", lg: "100vh" }}
      >
        <Heading
          as="h1"
          size={{ base: "2xl", lg: "3xl" }}
          fontFamily="heading"
          color="blue.300"
        >
          etolegko
        </Heading>
        <Text mt="3" color="gray.300" maxW="sm">
          Campaigns, streams, and offer weights
        </Text>
      </Flex>

      <Flex
        flex="1"
        align="center"
        justify="center"
        bg="bg.subtle"
        p="6"
        as="main"
      >
        <Box
          as="form"
          onSubmit={onSubmit}
          bg="bg"
          borderWidth="1px"
          borderColor="border.subtle"
          rounded="md"
          p="8"
          w="full"
          maxW="md"
        >
          <Heading as="h2" size="lg" color="blue.fg" mb="1">
            Sign in
          </Heading>
          <Text color="fg.muted" fontSize="sm" mb="6">
            Username and password
          </Text>
          <Stack gap="4">
            <Field.Root>
              <Field.Label>Username</Field.Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </Field.Root>
            <Field.Root>
              <Field.Label>Password</Field.Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </Field.Root>
            {error ? (
              <Text color="fg.error" fontSize="sm">
                {error}
              </Text>
            ) : null}
            <Button
              type="submit"
              size="sm"
              variant="solid"
              colorPalette="blue"
              loading={isLoading}
            >
              Sign in
            </Button>
          </Stack>
        </Box>
      </Flex>
    </Flex>
  );
}
