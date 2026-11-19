"use client";

import {
  Box,
  Button,
  CloseButton,
  Drawer,
  Flex,
  Heading,
  HStack,
  IconButton,
  Portal,
  Stack,
  Text,
} from "@chakra-ui/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { clearToken, getToken } from "@/lib/auth";

export type BreadcrumbItem = {
  label: string;
  href?: string;
};

type Props = {
  children: ReactNode;
  /** Plain header label (used when breadcrumbs omitted). */
  title?: string;
  /** Clickable crumbs; last item is current (no href). */
  breadcrumbs?: BreadcrumbItem[];
};

const NAV = [
  { href: "/companies", label: "Companies" },
  { href: "/offers", label: "Offers" },
];

function NavLinks({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <Stack gap="1" as="nav" aria-label="Main" w="full">
      {NAV.map((item) => {
        const active =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Button
            key={item.href}
            asChild
            size="sm"
            variant="ghost"
            justifyContent="flex-start"
            rounded="md"
            px="3"
            py="2"
            h="auto"
            fontWeight={active ? "medium" : "normal"}
            bg={active ? "gray.100" : "transparent"}
            color={active ? "gray.900" : "gray.fg"}
            onClick={onNavigate}
          >
            <Link href={item.href}>{item.label}</Link>
          </Button>
        );
      })}
    </Stack>
  );
}

function SidebarBody({
  pathname,
  onNavigate,
  onLogout,
}: {
  pathname: string;
  onNavigate?: () => void;
  onLogout: () => void;
}) {
  return (
    <Flex direction="column" h="full" px="3" py="5" gap="1">
      <Box mb="3">
        <Heading as="p" textStyle="md.semibold" color="blue.fg">
          etolegko
        </Heading>
        <Text textStyle="xs" color="fg.muted">
          Admin
        </Text>
      </Box>
      <NavLinks pathname={pathname} onNavigate={onNavigate} />
      <Box mt="auto" pt="4">
        <Button
          size="sm"
          variant="outline"
          colorPalette="cyan"
          w="full"
          onClick={onLogout}
        >
          Sign out
        </Button>
      </Box>
    </Flex>
  );
}

function HeaderBreadcrumbs({
  breadcrumbs,
  title,
}: {
  breadcrumbs?: BreadcrumbItem[];
  title?: string;
}) {
  if (breadcrumbs && breadcrumbs.length > 0) {
    return (
      <HStack
        as="nav"
        aria-label="Breadcrumb"
        gap="1"
        fontSize="sm"
        flexWrap="wrap"
      >
        {breadcrumbs.map((crumb, index) => {
          const isLast = index === breadcrumbs.length - 1;
          return (
            <HStack key={`${crumb.label}-${index}`} gap="1">
              {index > 0 ? (
                <Text as="span" color="fg.muted">
                  /
                </Text>
              ) : null}
              {crumb.href && !isLast ? (
                <Text as="span" color="blue.fg">
                  <Link href={crumb.href}>{crumb.label}</Link>
                </Text>
              ) : (
                <Text
                  as="span"
                  color={isLast ? "gray.fg" : "fg.muted"}
                  fontWeight={isLast ? "medium" : "normal"}
                >
                  {crumb.label}
                </Text>
              )}
            </HStack>
          );
        })}
      </HStack>
    );
  }
  return (
    <Text fontSize="sm" color="fg.muted">
      {title ?? "Admin"}
    </Text>
  );
}

export function AppShell({ children, title, breadcrumbs }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  function logout() {
    clearToken();
    router.replace("/login");
  }

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  return (
    <Flex minH="100vh" bg="bg.subtle">
      <Box
        as="aside"
        display={{ base: "none", md: "block" }}
        w={{ md: "200px", lg: "240px" }}
        borderRightWidth="1px"
        borderColor="border.subtle"
        bg="bg"
        flexShrink={0}
      >
        <SidebarBody pathname={pathname} onLogout={logout} />
      </Box>

      <Flex direction="column" flex="1" minW={0}>
        <HStack
          as="header"
          minH="11"
          px={{ base: "4", md: "6" }}
          py="3"
          borderBottomWidth="1px"
          borderColor="border.subtle"
          bg="bg"
          justify="space-between"
        >
          <HStack gap="2">
            <Drawer.Root
              open={open}
              onOpenChange={(d) => setOpen(d.open)}
              placement="start"
            >
              <Drawer.Trigger asChild>
                <IconButton
                  aria-label="Open menu"
                  size="sm"
                  variant="ghost"
                  display={{ base: "inline-flex", md: "none" }}
                >
                  ☰
                </IconButton>
              </Drawer.Trigger>
              <Portal>
                <Drawer.Backdrop />
                <Drawer.Positioner>
                  <Drawer.Content bg="bg" maxW="240px">
                    <Drawer.Header>
                      <Drawer.Title>Menu</Drawer.Title>
                      <Drawer.CloseTrigger asChild>
                        <CloseButton size="sm" />
                      </Drawer.CloseTrigger>
                    </Drawer.Header>
                    <Drawer.Body p="0">
                      <SidebarBody
                        pathname={pathname}
                        onNavigate={() => setOpen(false)}
                        onLogout={logout}
                      />
                    </Drawer.Body>
                  </Drawer.Content>
                </Drawer.Positioner>
              </Portal>
            </Drawer.Root>
            <HeaderBreadcrumbs breadcrumbs={breadcrumbs} title={title} />
          </HStack>
          <Text fontSize="sm" fontWeight="medium" color="gray.fg">
            admin
          </Text>
        </HStack>
        <Box
          as="main"
          flex="1"
          pt="6"
          px={{ base: "4", md: "6" }}
          pb="8"
        >
          {children}
        </Box>
      </Flex>
    </Flex>
  );
}
