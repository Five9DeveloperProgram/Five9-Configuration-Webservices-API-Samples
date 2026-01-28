# Five9 Configuration Webservices SOAP API from .NET 8 (Basic Auth)

Five9 Configuration Webservices is a SOAP (WSDL) API. .NET 8 doesn’t include the legacy “Add Service Reference” WCF tooling that older .NET Framework projects used, but you can still integrate in .NET 8 by:

1. Generating a client proxy from the WSDL, and
2. Using the WCF **client** NuGet packages at runtime.

This repo includes a static WSDL you can use for generation:

- `five9/static_resources/config_webservices_v13.wsdl`

The service endpoint in that WSDL is:

- `https://api.five9.com/wsadmin/v13/AdminWebService`

## Recommended approach: WCF client proxy + BasicHttpBinding

### 1) Generate the C# proxy from the WSDL

You have two common options.

#### Option A: Visual Studio “Connected Services” (Windows)

1. Right-click the project → **Add** → **Connected Service**
2. Choose **WCF Web Service Reference**
3. Point it at the WSDL file (local path) or a hosted URL
4. Choose a namespace (e.g., `Five9.WsAdmin`) and generate

This adds the generated client code to your project.

#### Option B: CLI using `dotnet-svcutil` (cross-platform)

Install the tool:

```bash
dotnet tool install --global dotnet-svcutil
```

Generate client code from the WSDL in this repo:

```bash
dotnet-svcutil five9/static_resources/config_webservices_v13.wsdl \
  --outputDir Generated/Five9 \
  --noLogo \
  -n "*,Five9.WsAdmin"
```

Then include the generated `.cs` files in your project (or move them into your source tree).

### 2) Add required NuGet packages

At minimum, most projects will need:

```bash
dotnet add package System.ServiceModel.Http
```

(That package brings in the WCF client implementation used by `BasicHttpBinding`.)

### 3) Call the API with HTTP Basic Auth on every request

If your Five9 tenant uses HTTP Basic Auth (username/password) per call, configure a `BasicHttpBinding` with transport security and Basic credentials.

```csharp
using System.ServiceModel;

// This namespace/type depends on how you generated the proxy.
using Five9.WsAdmin;

var binding = new BasicHttpBinding(BasicHttpSecurityMode.Transport);
binding.Security.Transport.ClientCredentialType = HttpClientCredentialType.Basic;

// Optional but common tuning for SOAP services
binding.MaxReceivedMessageSize = 10 * 1024 * 1024; // 10 MB; adjust as needed
// binding.ReaderQuotas = System.Xml.XmlDictionaryReaderQuotas.Max; // enable if needed

var endpoint = new EndpointAddress("https://api.five9.com/wsadmin/v13/AdminWebService");

var client = new WsAdminServiceClient(binding, endpoint);

client.ClientCredentials.UserName.UserName = five9Username;
client.ClientCredentials.UserName.Password = five9Password;

// Example call (choose any operation supported by the generated client)
var versions = await client.getApiVersionsAsync();
```

Notes:

- This setup sends the HTTP `Authorization: Basic ...` header as part of each request.
- You do **not** need a separate session/token if your integration is “Basic Auth per call”.

### Common troubleshooting

#### WSDL/XSD imports during generation

The WSDL imports an external schema:

- `https://raw.githubusercontent.com/apache/cxf/.../swaref.xsd`

If your build environment cannot reach that URL (offline build, restricted network), proxy generation may fail.

Workarounds:

- Run generation in an environment that can download the import, then check in the generated code; or
- Vendor the XSD locally and update the WSDL `schemaLocation` to point at the local file before generating.

#### Large responses / quota errors

If you see errors that look like message size/quota issues, increase:

- `binding.MaxReceivedMessageSize`
- `binding.ReaderQuotas` (careful: setting to `Max` increases allowed XML complexity)

#### TLS / certificate issues

The endpoint is HTTPS. If you get TLS/cert errors in lower environments, verify:

- The system trust store has the required CA certs
- Your corporate proxy is not intercepting TLS without trusted certs

## Fallback approach: raw SOAP over HttpClient

If your customer cannot use generated proxies for policy reasons, they can still integrate by sending raw SOAP XML.

High-level steps:

1. Build a SOAP 1.1 envelope XML for the operation
2. POST it to `https://api.five9.com/wsadmin/v13/AdminWebService`
3. Set headers:
   - `Content-Type: text/xml; charset=utf-8`
   - `SOAPAction: "..."` (varies by operation)
   - `Authorization: Basic base64(username:password)`
4. Parse the SOAP response XML

This works, but it’s more brittle and more work than using generated client code.

## Quick checklist to share with a customer

- Use `dotnet-svcutil` or VS Connected Services to generate a SOAP client from `config_webservices_v13.wsdl`
- Add `System.ServiceModel.Http`
- Use `BasicHttpBinding(BasicHttpSecurityMode.Transport)`
- Set `ClientCredentialType = HttpClientCredentialType.Basic`
- Set `ClientCredentials.UserName.UserName/Password`
- Call operations as async methods on the generated client
