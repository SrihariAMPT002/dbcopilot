import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { getRouter } from "./router";
import { Toaster } from "./components/ui/sonner";
import "./styles.css";

const router = getRouter();

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <RouterProvider router={router} />
      <Toaster richColors />
    </React.StrictMode>,
);
