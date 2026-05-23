import React from "react";
import { Navigate } from "react-router-dom";

import { getToken, TOKEN_ID } from "@/lib/queries/token";

type PublicRouteProps = {
  children: React.ReactNode;
};

const PublicRoute = ({ children }: PublicRouteProps) => {
  const apiUrl = getToken(TOKEN_ID.API_URL);
  const token = getToken(TOKEN_ID.TOKEN);
  const version = getToken(TOKEN_ID.VERSION);

  if (apiUrl && token && version) {
    return <Navigate to="/" />;
  }

  return children;
};

export default PublicRoute;
