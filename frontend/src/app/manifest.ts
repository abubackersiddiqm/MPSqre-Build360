import type { MetadataRoute } from "next";

import { domainBrandForCurrentHost } from "@/lib/branding/domain-brand";

export default async function manifest(): Promise<MetadataRoute.Manifest> {
  const mapped = await domainBrandForCurrentHost();
  const brand = mapped?.branding;
  const productName = brand?.product_name || "MPSqre Build360";
  const shortName = productName.length <= 24 ? productName : mapped?.company.display_name || "Build360";
  const iconUrl = brand?.compact_logo_url || brand?.favicon_url || "";
  const defaultIcons: MetadataRoute.Manifest["icons"] = [
    { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ];

  return {
    name: `${productName} — ${brand?.tagline || "Construction Operating System"}`,
    short_name: shortName,
    description: brand?.tagline || "Construction Operating System",
    start_url: mapped ? "/project360" : "/platform",
    scope: "/",
    display: "standalone",
    background_color: "#f6f7f9",
    theme_color: brand?.primary_color || "#174d3c",
    orientation: "any",
    categories: ["business", "productivity"],
    icons: iconUrl ? [{ src: iconUrl, sizes: "any", purpose: "any" }] : defaultIcons,
    shortcuts: [
      {
        name: "Project 360",
        short_name: "Projects",
        description: "Open the visual project operating journey.",
        url: "/project360",
        icons: iconUrl ? [{ src: iconUrl, sizes: "any" }] : [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
      {
        name: "Field operations",
        short_name: "Field",
        description: "Open labour, equipment, quality and safety operations.",
        url: "/field-operations",
        icons: iconUrl ? [{ src: iconUrl, sizes: "any" }] : [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
    ],
  };
}
