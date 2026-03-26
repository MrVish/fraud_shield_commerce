import { useState, useCallback } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useActionData, useSubmit, useNavigation } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  Checkbox,
  ChoiceList,
  Select,
  TextField,
  Button,
  Banner,
  InlineStack,
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
  const settingsJson = formData.get("settings") as string;

  try {
    const settingsData = JSON.parse(settingsJson);
    await updateMerchantSettings(1, { settings: settingsData });
    return { success: true } satisfies ActionData;
  } catch (e) {
    console.error("[ShieldCommerce] Settings update error:", e);
    return { error: "Failed to save settings." } satisfies ActionData;
  }
};

export default function Settings() {
  const { settings: loadedSettings, error: loadError } = useLoaderData<LoaderData>();
  const actionData = useActionData<ActionData>();
  const submit = useSubmit();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  const current = loadedSettings ?? defaultSettings;

  const [emailAlertsEnabled, setEmailAlertsEnabled] = useState(current.settings.email_alerts_enabled);
  const [alertRiskLevels, setAlertRiskLevels] = useState<string[]>(current.settings.alert_on_risk_levels);
  const [digestFrequency, setDigestFrequency] = useState(current.settings.digest_frequency);
  const [digestEmail, setDigestEmail] = useState(current.settings.digest_email);

  const handleSave = useCallback(() => {
    const formData = new FormData();
    formData.set(
      "settings",
      JSON.stringify({
        email_alerts_enabled: emailAlertsEnabled,
        alert_on_risk_levels: alertRiskLevels,
        digest_frequency: digestFrequency,
        digest_email: digestEmail,
      }),
    );
    submit(formData, { method: "POST" });
  }, [emailAlertsEnabled, alertRiskLevels, digestFrequency, digestEmail, submit]);

  return (
    <Page>
      <TitleBar title="Notification Settings" />
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
          <Layout.AnnotatedSection
            title="Email Alerts"
            description="Configure when and how you receive fraud alert notifications."
          >
            <Card>
              <BlockStack gap="400">
                <Checkbox
                  label="Enable email alerts"
                  checked={emailAlertsEnabled}
                  onChange={setEmailAlertsEnabled}
                />

                <ChoiceList
                  title="Alert on risk levels"
                  allowMultiple
                  choices={[
                    { label: "Low", value: "low" },
                    { label: "Medium", value: "medium" },
                    { label: "High", value: "high" },
                    { label: "Critical", value: "critical" },
                  ]}
                  selected={alertRiskLevels}
                  onChange={setAlertRiskLevels}
                />
              </BlockStack>
            </Card>
          </Layout.AnnotatedSection>

          <Layout.AnnotatedSection
            title="Digest Settings"
            description="Set up periodic summary emails about your store's fraud activity."
          >
            <Card>
              <BlockStack gap="400">
                <Select
                  label="Digest frequency"
                  options={[
                    { label: "Daily", value: "daily" },
                    { label: "Weekly", value: "weekly" },
                    { label: "Off", value: "off" },
                  ]}
                  value={digestFrequency}
                  onChange={setDigestFrequency}
                />

                <TextField
                  label="Digest email address"
                  type="email"
                  value={digestEmail}
                  onChange={setDigestEmail}
                  autoComplete="email"
                  placeholder="alerts@yourstore.com"
                />
              </BlockStack>
            </Card>
          </Layout.AnnotatedSection>
        </Layout>

        <InlineStack align="end">
          <Button variant="primary" onClick={handleSave} loading={isSubmitting}>
            Save Settings
          </Button>
        </InlineStack>
      </BlockStack>
    </Page>
  );
}
