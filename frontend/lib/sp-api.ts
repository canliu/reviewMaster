import { api } from "@/lib/api";

export interface SpApiCredentialsMetadata {
  configured: boolean;
  lwa_client_id_prefix: string | null;
  selling_partner_id: string | null;
  marketplace_id: string | null;
  marketplace_label: string | null;
  updated_at: string | null;
}

export interface SpApiCredentialsIn {
  lwa_client_id: string;
  lwa_client_secret: string;
  refresh_token: string;
  selling_partner_id: string;
  marketplace_id: string;
}

export type TestConnectionResult =
  | { ok: true; marketplaces: string[]; elapsed_ms: number }
  | { ok: false; error_code: string; message: string };

// Same list as the backend's MARKETPLACES dict — kept in sync by hand.
export const SP_API_MARKETPLACES: ReadonlyArray<{ id: string; label: string }> = [
  { id: "ATVPDKIKX0DER", label: "Amazon.com (US)" },
  { id: "A2EUQ1WTGCTBG2", label: "Amazon.ca (CA)" },
  { id: "A1AM78C64UM0Y8", label: "Amazon.com.mx (MX)" },
  { id: "A2Q3Y263D00KWC", label: "Amazon.com.br (BR)" },
  { id: "A1F83G8C2ARO7P", label: "Amazon.co.uk (UK)" },
  { id: "A1PA6795UKMFR9", label: "Amazon.de (DE)" },
  { id: "A13V1IB3VIYZZH", label: "Amazon.fr (FR)" },
  { id: "APJ6JRA9NG5V4", label: "Amazon.it (IT)" },
  { id: "A1RKKUPIHCS9HS", label: "Amazon.es (ES)" },
  { id: "A1805IZSGTT6HS", label: "Amazon.nl (NL)" },
  { id: "A2NODRKZP88ZB9", label: "Amazon.se (SE)" },
  { id: "A1C3SOZRARQ6R3", label: "Amazon.pl (PL)" },
  { id: "A33AVAJ2PDY3EV", label: "Amazon.com.tr (TR)" },
  { id: "A2VIGQ35RCS4UG", label: "Amazon.ae (AE)" },
  { id: "A17E79C6D8DWNP", label: "Amazon.sa (SA)" },
  { id: "ARBP9OOSHTCHU", label: "Amazon.eg (EG)" },
  { id: "A1VC38T7YXB528", label: "Amazon.co.jp (JP)" },
  { id: "A39IBJ37TRP1C6", label: "Amazon.com.au (AU)" },
  { id: "A19VAU5U5O7RUS", label: "Amazon.sg (SG)" },
  { id: "A21TJRUUN4KGV", label: "Amazon.in (IN)" },
];

export async function getSpApiCredentials(): Promise<SpApiCredentialsMetadata> {
  const { data } = await api.get<SpApiCredentialsMetadata>(
    "/api/sp-api/credentials",
  );
  return data;
}

export async function saveSpApiCredentials(
  body: SpApiCredentialsIn,
): Promise<SpApiCredentialsMetadata> {
  const { data } = await api.post<SpApiCredentialsMetadata>(
    "/api/sp-api/credentials",
    body,
  );
  return data;
}

export async function deleteSpApiCredentials(): Promise<void> {
  await api.delete("/api/sp-api/credentials");
}

export async function testSpApiConnection(): Promise<TestConnectionResult> {
  const { data } = await api.post<TestConnectionResult>(
    "/api/sp-api/test-connection",
  );
  return data;
}
