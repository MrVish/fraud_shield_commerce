import { useState, useCallback } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useActionData, useSubmit, useNavigation } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  RangeSlider,
  TextField,
  Button,
  Tag,
  InlineStack,
  Banner,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { getMerchantSettings, updateMerchantSettings } from "../lib/scoring-api.server";
import type { MerchantSettings } from "../lib/types";

interface LoaderData {
  settings: MerchantSettings | null;
  error: string | null;
}

interface ActionData {
  success?: boolean;
  error?: string;
}

const defaultSettings: MerchantSettings = {
  thresholds: {
    low_max: 30,
    medium_max: 60,
    high_max: 85,
    auto_approve_below: 20,
    auto_cancel_above: 95,
  },
  settings: {
    email_alerts_enabled: false,
    alert_on_risk_levels: [],
    digest_frequency: "daily",
    digest_email: "",
  },
};

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  try {
    const settings = await getMerchantSettings(1);
    return { settings, error: null } satisfies LoaderData;
  } catch (e) {
    console.error("[ShieldCommerce] Settings load error:", e);
    return {
      settings: null,
      error: "Unable to load settings. Using defaults.",
    } satisfies LoaderData;
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  await authenticate.admin(request);

  const formData = await request.formData();
  const thresholdsJson = formData.get("thresholds") as string;

  try {
    const thresholds = JSON.parse(thresholdsJson);
    await updateMerchantSettings(1, { thresholds });
    return { success: true } satisfies ActionData;
  } catch (e) {
    console.error("[ShieldCommerce] Settings update error:", e);
    return { error: "Failed to save settings." } satisfies ActionData;
  }
};

export default function Rules() {
  const { settings: loadedSettings, error: loadError } = useLoaderData<LoaderData>();
  const actionData = useActionData<ActionData>();
  const submit = useSubmit();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  const settings = loadedSettings ?? defaultSettings;

  const [lowMax, setLowMax] = useState(settings.thresholds.low_max);
  const [mediumMax, setMediumMax] = useState(settings.thresholds.medium_max);
  const [highMax, setHighMax] = useState(settings.thresholds.high_max);
  const [autoApprove, setAutoApprove] = useState(settings.thresholds.auto_approve_below);
  const [autoCancel, setAutoCancel] = useState(settings.thresholds.auto_cancel_above);

  const [whitelistInput, setWhitelistInput] = useState("");
  const [whitelist, setWhitelist] = useState<string[]>([]);
  const [blacklistInput, setBlacklistInput] = useState("");
  const [blacklist, setBlacklist] = useState<string[]>([]);

  const addToWhitelist = useCallback(() => {
    if (whitelistInput.trim() && !whitelist.includes(whitelistInput.trim())) {
      setWhitelist((prev) => [...prev, whitelistInput.trim()]);
      setWhitelistInput("");
    }
  }, [whitelistInput, whitelist]);

  const removeFromWhitelist = useCallback((entry: string) => {
    setWhitelist((prev) => prev.filter((e) => e !== entry));
  }, []);

  const addToBlacklist = useCallback(() => {
    if (blacklistInput.trim() && !blacklist.includes(blacklistInput.trim())) {
      setBlacklist((prev) => [...prev, blacklistInput.trim()]);
      setBlacklistInput("");
    }
  }, [blacklistInput, blacklist]);

  const removeFromBlacklist = useCallback((entry: string) => {
    setBlacklist((prev) => prev.filter((e) => e !== entry));
  }, []);

  const handleSave = useCallback(() => {
    const formData = new FormData();
    formData.set(
      "thresholds",
      JSON.stringify({
        low_max: lowMax,
        medium_max: mediumMax,
        high_max: highMax,
        auto_approve_below: autoApprove,
        auto_cancel_above: autoCancel,
      }),
    );
    submit(formData, { method: "POST" });
  }, [lowMax, mediumMax, highMax, autoApprove, autoCancel, submit]);

  return (
    <Page>
      <TitleBar title="Risk Rules & Thresholds" />
      <BlockStack gap="500">
        {loadError && (
          <Banner tone="warning">
            <p>{loadError}</p>
          </Banner>
        )}
        {actionData?.success && (
          <Banner tone="success">
            <p>Settings saved successfully.</p>
          </Banner>
        )}
        {actionData?.error && (
          <Banner tone="critical">
            <p>{actionData.error}</p>
          </Banner>
        )}

        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Risk Score Thresholds
                </Text>
                <RangeSlider
                  label={`Low Max: ${lowMax}`}
                  value={lowMax}
                  min={0}
                  max={100}
                  onChange={(val) => setLowMax(val as number)}
                  output
                />
                <RangeSlider
                  label={`Medium Max: ${mediumMax}`}
                  value={mediumMax}
                  min={0}
                  max={100}
                  onChange={(val) => setMediumMax(val as number)}
                  output
                />
                <RangeSlider
                  label={`High Max: ${highMax}`}
                  value={highMax}
                  min={0}
                  max={100}
                  onChange={(val) => setHighMax(val as number)}
                  output
                />
              </BlockStack>
            </Card>
          </Layout.Section>

          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Automation
                </Text>
                <RangeSlider
                  label={`Auto-approve below: ${autoApprove}`}
                  value={autoApprove}
                  min={0}
                  max={100}
                  onChange={(val) => setAutoApprove(val as number)}
                  output
                />
                <RangeSlider
                  label={`Auto-cancel above: ${autoCancel}`}
                  value={autoCancel}
                  min={0}
                  max={100}
                  onChange={(val) => setAutoCancel(val as number)}
                  output
                />
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Email Whitelist
                </Text>
                <InlineStack gap="200" blockAlign="end">
                  <div style={{ flexGrow: 1 }}>
                    <TextField
                      label="Add email or domain"
                      value={whitelistInput}
                      onChange={setWhitelistInput}
                      autoComplete="off"
                      placeholder="e.g., trusted@example.com or @trustedco.com"
                    />
                  </div>
                  <Button onClick={addToWhitelist}>Add</Button>
                </InlineStack>
                <InlineStack gap="200">
                  {whitelist.map((entry) => (
                    <Tag key={entry} onRemove={() => removeFromWhitelist(entry)}>
                      {entry}
                    </Tag>
                  ))}
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Email Blacklist
                </Text>
                <InlineStack gap="200" blockAlign="end">
                  <div style={{ flexGrow: 1 }}>
                    <TextField
                      label="Add email or domain"
                      value={blacklistInput}
                      onChange={setBlacklistInput}
                      autoComplete="off"
                      placeholder="e.g., scammer@fraud.com"
                    />
                  </div>
                  <Button onClick={addToBlacklist}>Add</Button>
                </InlineStack>
                <InlineStack gap="200">
                  {blacklist.map((entry) => (
                    <Tag key={entry} onRemove={() => removeFromBlacklist(entry)}>
                      {entry}
                    </Tag>
                  ))}
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        <InlineStack align="end">
          <Button variant="primary" onClick={handleSave} loading={isSubmitting}>
            Save Rules
          </Button>
        </InlineStack>
      </BlockStack>
    </Page>
  );
}
