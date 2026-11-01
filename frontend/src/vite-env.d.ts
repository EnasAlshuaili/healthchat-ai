/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional prefix for API requests. Leave unset in local development (the Vite proxy is used). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
