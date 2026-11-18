<#
.SYNOPSIS
Creates a self-signed internal Authenticode Code Signing certificate for Ohr HaKsav
suitable for Windows Active Directory Domain deployment (e.g., via GPO Trusted Root & Trusted Publishers).

.DESCRIPTION
Run this script on a secure admin workstation (NOT on a production domain controller).
It generates:
  1. A code-signing certificate in Cert:\CurrentUser\My
  2. Exports the public .cer file (deploy to domain PCs via GPO -> Trusted Root & Trusted Publishers)
  3. Prints the exact environment variable (OHR_HAKSAV_CERT_THUMBPRINT) to pass to build_exe.py
     so future builds are automatically signed with SHA-256 Authenticode!
#>

param(
    [string]$Subject = "CN=Torah uMesorah Lakewood Teachers Center - Ohr HaKsav Code Signing",
    [string]$ExportCerPath = ".\OhrHaKsav_Internal_CodeSign.cer",
    [int]$ValidYears = 5
)

$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject $Subject `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyAlgorithm RSA `
    -KeyLength 3072 `
    -HashAlgorithm SHA256 `
    -NotAfter (Get-Date).AddYears($ValidYears)

Export-Certificate -Cert $cert -FilePath $ExportCerPath -Force | Out-Null

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host " Internal Code Signing Certificate Created Successfully!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "Thumbprint : $($cert.Thumbprint)"
Write-Host "Public CER : $(Resolve-Path $ExportCerPath)"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. To sign builds automatically, run before building:"
Write-Host "       `$env:OHR_HAKSAV_CERT_THUMBPRINT = '$($cert.Thumbprint)'"
Write-Host "       python build_exe.py"
Write-Host "  2. For domain workstations, distribute the .cer file via Group Policy:"
Write-Host "       Computer Configuration -> Policies -> Windows Settings -> Security Settings ->"
Write-Host "       Public Key Policies -> Trusted Root Certification Authorities & Trusted Publishers"
Write-Host ""
