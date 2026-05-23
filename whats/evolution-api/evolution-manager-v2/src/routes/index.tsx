import { createBrowserRouter } from "react-router-dom";

import ProtectedRoute from "@/components/providers/protected-route";
import PublicRoute from "@/components/providers/public-route";

import { InstanceLayout } from "@/layout/InstanceLayout";
import { MainLayout } from "@/layout/MainLayout";

import Dashboard from "@/pages/Dashboard";
import { Chat } from "@/pages/instance/Chat";
import { Chatwoot } from "@/pages/instance/Chatwoot";
import { DashboardInstance } from "@/pages/instance/DashboardInstance";
import { Dify } from "@/pages/instance/Dify";
import { EmbedChat } from "@/pages/instance/EmbedChat";
import { Evoai } from "@/pages/instance/Evoai";
import { EvolutionBot } from "@/pages/instance/EvolutionBot";
import { Flowise } from "@/pages/instance/Flowise";
import { N8n } from "@/pages/instance/N8n";
import { Openai } from "@/pages/instance/Openai";
import { Proxy } from "@/pages/instance/Proxy";
import { Rabbitmq } from "@/pages/instance/Rabbitmq";
import { Settings } from "@/pages/instance/Settings";
import { Sqs } from "@/pages/instance/Sqs";
import { Typebot } from "@/pages/instance/Typebot";
import { Webhook } from "@/pages/instance/Webhook";
import { Websocket } from "@/pages/instance/Websocket";
import Login from "@/pages/Login";
import Home from "@/pages/Home";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Home />,
  },
  {
    path: "/manager/login",
    element: (
      <PublicRoute>
        <Login />
      </PublicRoute>
    ),
  },
  {
    path: "/manager/",
    element: (
      <ProtectedRoute>
        <MainLayout>
          <Dashboard />
        </MainLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/dashboard",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <DashboardInstance />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/chat",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Chat />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/chat/:remoteJid",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Chat />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/settings",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Settings />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/openai",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Openai />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/openai/:botId",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Openai />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/webhook",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Webhook />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/websocket",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Websocket />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/rabbitmq",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Rabbitmq />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/sqs",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Sqs />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/chatwoot",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Chatwoot />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/typebot",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Typebot />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/typebot/:typebotId",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Typebot />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/dify",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Dify />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/dify/:difyId",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Dify />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/n8n",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <N8n />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/n8n/:n8nId",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <N8n />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/evoai",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Evoai />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/evoai/:evoaiId",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Evoai />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/evolutionBot",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <EvolutionBot />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/evolutionBot/:evolutionBotId",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <EvolutionBot />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/flowise",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Flowise />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/flowise/:flowiseId",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Flowise />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/instance/:instanceId/proxy",
    element: (
      <ProtectedRoute>
        <InstanceLayout>
          <Proxy />
        </InstanceLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/manager/embed-chat",
    element: <EmbedChat />,
  },
  {
    path: "/manager/embed-chat/:remoteJid",
    element: <EmbedChat />,
  },
]);

export default router;
