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
import { toastMutation } from "@/lib/toastMutation";
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
      const res = await toastMutation(
        login({ username, password }).unwrap(),
        {
          loading: "Signing in…",
          success: "Signed in",
          errorTitle: "Login failed",
        },
      );
      setToken(res.access_token);
      router.replace("/companies");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Flex minH="100vh" direction={{ base: "column", md: "row" }}>
      <Flex
        display={{ base: "none", md: "flex" }}
        w={{ md: "280px", lg: "520px" }}
        flexShrink={0}
        bg="blue.subtle"
        color="blue.fg"
        pt="12"
        px="10"
        direction="column"
        gap="3"
        as="aside"
        aria-label="Brand"
      >
        <Heading as="h1" textStyle="brand" color="blue.fg">
          etolegko
        </Heading>
        <Text textStyle="brand.subtitle" color="blue.fg">
          Campaigns, streams, and offer weights
        </Text>
      </Flex>

      <Flex
        flex="1"
        align="center"
        justify="center"
        bg="bg.subtle"
        p={{ base: "4", md: "6" }}
        as="main"
      >
        <Box
          as="form"
          onSubmit={onSubmit}
          bg="bg"
          borderWidth="1px"
          borderColor="border.subtle"
          rounded="xl"
          px="6"
          py="7"
          w="full"
          maxW="380px"
        >
          <Heading as="h2" textStyle="cardTitle" color="gray.fg" mb="1">
            <Box as="span" display={{ base: "inline", md: "none" }}>
              etolegko
            </Box>
            <Box as="span" display={{ base: "none", md: "inline" }}>
              Sign in
            </Box>
          </Heading>
          <Text color="fg.muted" textStyle="muted" mb="4">
            Username and password
          </Text>
          <Stack gap="3.5">
            <Field.Root>
              <Field.Label srOnly>Username</Field.Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="admin"
                aria-label="Username"
              />
            </Field.Root>
            <Field.Root>
              <Field.Label srOnly>Password</Field.Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
                aria-label="Password"
              />
            </Field.Root>
            {error ? (
              <Text color="fg.error" textStyle="sm">
                {error}
              </Text>
            ) : null}
            <Button
              type="submit"
              size="sm"
              variant="solid"
              colorPalette="blue"
              w="full"
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
