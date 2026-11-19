"use client";

import { Box, Heading, Text } from "@chakra-ui/react";

export default function HomePage() {
  return (
    <Box as="main" minH="100vh" bg="bg.subtle" color="gray.fg" p="8">
      <Heading as="h1" size="2xl" color="blue.fg" fontFamily="heading">
        etolegko
      </Heading>
      <Text color="fg.muted" mt="2">
        Frontend shell. API screens come next.
      </Text>
    </Box>
  );
}
