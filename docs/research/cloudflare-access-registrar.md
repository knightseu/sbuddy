# Cloudflare Access and Registrar for the Sbuddy viewer

Research for issue #41, a child of map #40. Checked 2026-11-24 against Cloudflare's own docs and pricing pages.

**Scope.** The viewer will be cloud-hosted (the host is chosen in a separate ticket). This note covers only:

- Cloudflare Access gating the site for a few invited users.
- Cloudflare Registrar and DNS for a newly bought domain.

Cloudflare Tunnel and hosting on the Mac were dropped from scope, and hosts are not compared here.

**Short answer.**

- **Access.** The Zero Trust Free plan covers up to 50 users at $0. Logins can be by emailed one-time PIN, Google, or both. Sessions default to 24 hours and can be set as long as one month.
- **Origin protection.** Access only protects traffic that goes through Cloudflare. Anyone who knows the host's own URL can skip it unless the app checks the Access JWT itself.
- **Registrar.** Domains are sold at cost and are always on Cloudflare nameservers. A domain bought there needs no nameserver change, so the activation wait does not apply.
- **Cost.** For this use, nothing needs a paid Cloudflare plan. The one spend is the domain, about $11 to $14 a year for the likely TLDs.

## 1. Cloudflare Access

### Plan and seats

| Fact | Value | Source |
|---|---|---|
| Zero Trust Free plan | "$0 forever", user limit "50 users", for "Teams under 50 users" | https://www.cloudflare.com/plans/sase-zero-trust.md |
| Pay-as-you-go plan | $7 /user/month, "Teams over 50" | https://www.cloudflare.com/plans/sase-zero-trust.md |
| Free plan log retention / support | "Up to 24 hours"; "Community forums + Discord" | https://www.cloudflare.com/plans/sase-zero-trust.md |
| Free plan includes ZTNA (Access) | "Zero Trust Network Access: Included" | https://www.cloudflare.com/plans/sase-zero-trust.md |
| Payment details at signup | Required even on Free: "If you chose the Zero Trust Free plan, this step is still needed but you will not be charged." | https://developers.cloudflare.com/cloudflare-one/setup/ |
| What uses a seat | "A user consumes a seat when they perform an authentication event". One seat per user, however many apps or logins. | https://developers.cloudflare.com/cloudflare-one/team-and-resources/users/seat-management/ |
| When seats run out | Users who try to log in are blocked | https://developers.cloudflare.com/cloudflare-one/team-and-resources/users/seat-management/ |
| Freeing seats | Removing a user frees the seat. Revoking only ends sessions and keeps the seat. Optional seat expiration (off by default) frees inactive users after 1 month to 1 year. | https://developers.cloudflare.com/cloudflare-one/team-and-resources/users/seat-management/ |
| Account limits | 500 Access applications, 1,000 rules per application, 1,000 email addresses per rule, 50 identity providers. Not broken out by plan. | https://developers.cloudflare.com/cloudflare-one/account-limits/ |

The pricing page does not say what happens when a Free account goes past 50 users. Community forum posts (not official) say Pay-as-you-go bills every seat, not only those above 50. Keep the invite list well under 50, and use seat expiration or removal to reclaim seats.

### Login methods

- **One-time PIN (email).**
  - The code is single-use and "expires 10 minutes after the initial request".
  - "Cloudflare only sends the email if the user is allowed by an Access policy". A blocked user sees the same "code has been emailed" screen but gets nothing.
  - Email security scanners can use up the link before the user does. The fix is to request a new code.
  - OTP can be on at the same time as another IdP, and the user picks which one to use.
  - Source: https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/
- **Google (consumer Gmail works, no Workspace needed).**
  - Setup needs a Google Cloud project with an "External" OAuth consent screen and a Web application OAuth client.
  - Authorized origin: `https://<team-name>.cloudflareaccess.com`
  - Redirect URI: `https://<team-name>.cloudflareaccess.com/cdn-cgi/access/callback`
  - Source: https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/google/

OTP needs no setup outside Cloudflare, so it is enough for a few invited users. Google is optional.

### Session length

- **Application session.** "Available session durations range from immediate timeout to one month. The default value is 24 hours."
- **Global session** (SSO across Access apps). "between 15 minutes and one month. The default value is 24 hours."
- Access checks sessions from most to least specific: client, policy, application, global.
- Source: https://developers.cloudflare.com/cloudflare-one/access-controls/access-settings/session-management/

Two `CF_Authorization` cookies hold the tokens:

- **Team domain cookie.** Holds the global token.
- **App hostname cookie.** Holds the application token, HttpOnly, SameSite default None. If no duration is set, it expires after 24 hours.
- Source: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/

### Reading the authenticated user in the app

- **Use the JWT.** Access "includes the application token with all authenticated requests to your origin". For identity-based logins the payload has `email` ("verified by the identity provider"), plus `aud`, `iss`, `exp`, `nbf`, `iat`, `sub` and `country`. Service-token logins carry no email. For more identity data (such as groups), send the cookie to `/cdn-cgi/access/get-identity`. Source: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/application-token/
- **How to validate it.** Source: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
  - Read the `Cf-Access-Jwt-Assertion` header, not the cookie, because the cookie "is not guaranteed to be passed".
  - Check the signature against `https://<team-name>.cloudflareaccess.com/cdn-cgi/access/certs`. Pick the key by `kid` from `public_certs`.
  - Check that `aud` contains the app's AUD tag and `iss` is the team domain. Check `exp` and `nbf`.
  - The page warns: "A valid signature alone does not establish that the token is valid for your application."
- **`Cf-Access-Authenticated-User-Email` header.** It appears only in tutorial examples, such as a Worker reading `cf-access-authenticated-user-email` (https://developers.cloudflare.com/cloudflare-one/tutorials/access-workers/). The reference docs do not describe it, and it is not signed. Use it for display at most, never for authorization.

In Express this is small middleware: verify the header with a JWKS client such as `jose`'s `createRemoteJWKSet`, then put `payload.email` on `req`.

### Protecting an app on a third-party origin

Source: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/

- **Prerequisites.** "An active domain on Cloudflare", with a full setup or a partial (CNAME) setup.
- **Partial setup.** This is "only available to customers on a Business or Enterprise plan" (https://developers.cloudflare.com/dns/zone-setups/partial-setup/). A Free-plan zone must be a full setup, which a Registrar domain always is.
- **Creating the app.**
  - Add a Self-hosted application for the public hostname and attach an Allow policy (apps deny by default).
  - Choose the identity providers and set the session duration.
  - The hostname must be a proxied (orange-cloud) DNS record, for example a CNAME to the host's app URL, so that traffic passes through Cloudflare.
- **Origin bypass.** The page says: "If your application is already publicly routable, a tunnel is not strictly required", but "you will then need to protect your origin IP using other methods." Its stated way to reject requests that skip Access is to "manually validate the application token at your origin".
  - For a cloud host, the default URL (such as `*.example-host.app`) is publicly routable and skips Access entirely.
  - So the app should reject any request without a valid `Cf-Access-Jwt-Assertion` (exempt only the health check).
  - The alternative is to disable the host's default URL, if the host allows that.
- **Host that also runs on Cloudflare (Cloudflare for SaaS).** Then "Orange-to-Orange" applies: with a proxied record in our zone, "the settings configured in your Cloudflare zone will be applied to the traffic first", then the provider's. O2O needs our record to be proxied. The page does not mention Access by name, so the hosting ticket should confirm that Access works with the chosen host. Source: https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/saas-customers/how-it-works/

## 2. Registrar and DNS

### What Registrar gives

- **Pricing.**
  - "Registration, transfer, and renewal prices are always at or below what registries and ICANN charge us." (https://www.cloudflare.com/products/registrar/)
  - "Cloudflare Registrar does not mark up domain prices at all." (same page)
  - "over 430 top-level domains" are supported (same page).
- **Free features.**
  - "Free WHOIS redaction keeps your personal contact details out of public records." (https://www.cloudflare.com/products/registrar/)
  - DNSSEC is one click, at no cost (https://developers.cloudflare.com/registrar/).
  - Domains auto-renew by default (https://developers.cloudflare.com/registrar/).
- **Nameserver lock-in.** "All domains acquired via Cloudflare Registrar use Cloudflare nameservers". Using other DNS means moving to another registrar. Sources: https://developers.cloudflare.com/registrar/get-started/register-domain/ and https://developers.cloudflare.com/registrar/faq/
- **Other fees.** Redeeming an expired domain carries a separate restore fee (https://developers.cloudflare.com/registrar/faq/).

### Prices for likely TLDs (USD per year)

The official table is https://pricing.registrar.cloudflare.com/. It returns HTTP 403 to automated fetches, so the figures below come from the search-index copy of that page. Treat them as approximate and confirm in the dashboard's Register domains flow before buying.

| TLD | Price (renewal) | Notes |
|---|---|---|
| .com | $11.17 (register = renew = transfer; restore $40.00) | |
| .org | $11.20 | A third-party mirror (cfdomainpricing.com, not primary) shows a lower first-year price of $8.50 |
| .dev | $12.20 | "All websites on the .dev TLD are required to use HTTPS" (https://www.cloudflare.com/application-services/products/registrar/buy-dev-domains/) |
| .app | $14.20 | "The .app domain requires a secure HTTPS connection to work in browsers." (https://www.cloudflare.com/application-services/products/registrar/buy-app-domains/) |

The HTTPS-only rule for .app and .dev does not matter here, because the proxied hostname gets Universal SSL anyway. Future price changes are listed at https://pricing.registrar.cloudflare.com/price-changes (also blocked to fetches).

### Buying a domain and putting it on Cloudflare

1. **Create a Cloudflare account** with a verified email address: "You must have a verified account email address, to transfer or register domains." Source: https://developers.cloudflare.com/registrar/get-started/register-domain/
2. **Buy the domain.** Go to Register domains, search, choose a term, and enter contact details (ASCII only). Then pick a payment method, accept the Domain Registration Agreement and the Self-serve Subscription Agreement, and complete the purchase. "Registration can take up to 30 seconds." Internationalized domain names are not supported. Source: same page.
3. **DNS is already on Cloudflare.** The domain uses Cloudflare nameservers from the start, so there is no nameserver change.
4. **Choose the zone plan.** The Free plan is "$0" and includes DNS, CDN, Universal SSL, unmetered DDoS protection, WAF, and "70 rules + 10K Bulk Redirects". Pro is "$25/mo billed monthly" and is not needed. Source: https://www.cloudflare.com/plans/network-cdn.md

If the domain were bought elsewhere instead, you would follow https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/:

- Onboard the domain, review its DNS records, and turn off DNSSEC at the old registrar.
- Change the nameservers to the pair Cloudflare assigns. "Wait up to 24 hours while your registrar updates your nameservers." The domain is active when Cloudflare emails you and the Domains page shows **Active**. Then re-enable DNSSEC.
- Cloudflare's first nameserver check comes "after 60 seconds", then at "gradually increased intervals". A check can also be triggered by hand.
- A Free zone is deleted if "it is not activated within 28 days". Source: https://developers.cloudflare.com/dns/zone-setups/reference/domain-status/

## 3. Proxy limits that apply to any proxied hostname

| Limit | Value | Source |
|---|---|---|
| Max request body (upload), Free/Pro | 100 MB, error 413 | https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413 |
| Proxy read timeout (origin to first byte) | 125 s, error 524, configurable only on Enterprise | https://developers.cloudflare.com/fundamentals/reference/connection-limits/ |
| Request / response headers | 128 KB each; URL 16 KB | https://developers.cloudflare.com/fundamentals/reference/connection-limits/ |
| Default caching | PNG and SVG cached by extension; "does not cache HTML or JSON by default"; max cacheable file 512 MB on Free | https://developers.cloudflare.com/cache/concepts/default-cache-behavior/ |
| CDN media terms | Cloudflare may limit the CDN if it is used "without such Paid Services to serve video" or "a disproportionate percentage of pictures, audio files, or other large files" (terms updated 2026-09-28) | https://www.cloudflare.com/service-specific-terms-application-services/ |

The roughly 7 MB of figures is a small part of an app that mostly serves HTML and JSON, so the media clause should not apply.

## 4. Things that would need a paid plan

- **More than 50 Access users.** This moves to Pay-as-you-go at $7/user/month, and community reports say every seat is billed.
- **Access log retention beyond 24 hours.** Free keeps logs for "Up to 24 hours".
- **Partial (CNAME) DNS setup**, which would keep DNS at another provider. Business or Enterprise only. This is moot with Registrar.
- **A longer proxy read timeout than 125 s.** Enterprise only.
- **Uploads over 100 MB.** Business or above.

Nothing in the current viewer needs any of these.

## Recommendation for this stack

1. **Domain.** Buy it through Cloudflare Registrar. `.com` is about $11/year and has no HTTPS-only browser rule. DNS is on Cloudflare at once, so there is no nameserver wait, and WHOIS redaction is free. Keep the zone on the Free plan.
2. **Access organization.** Create a Zero Trust organization on the Free plan. A card is required but not charged. Use email OTP as the login method, and add Google only if someone asks. Set the application session to something like 1 week to 1 month so invited users are not prompted daily.
3. **Policy.** Add a single Self-hosted Access application on the viewer hostname with an Allow policy listing the invited emails. Optionally turn on seat expiration so stale users free up seats.
4. **Origin check.** Point the hostname at the host with a proxied CNAME. Add Express middleware that validates `Cf-Access-Jwt-Assertion` (team certs URL, AUD tag, issuer) and rejects everything else except the health check. This closes the bypass through the host's own default URL. It also gives the app `payload.email` if it later wants per-user features. Do not trust `Cf-Access-Authenticated-User-Email` on its own.
5. **Questions for the hosting ticket.**
   - Can the host's default public URL be disabled? If yes, keep JWT validation as defense in depth. If no, JWT validation is the only control on that URL.
   - Is the host itself on Cloudflare (O2O)? If so, check that Access behaves as expected in front of it.

Expected Cloudflare cost: $0/month, plus the domain at about $11 to $14/year.
