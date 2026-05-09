import urllib.request, json

cookies = [
    {"name": "_fbp", "value": "fb.1.1774466062447.326382480823280847"},
    {"name": "intercom-device-id-esc25l7u", "value": "86061d88-6a98-49f3-afde-07721a473f49"},
    {"name": "__Secure-better-auth.session_token", "value": "0ElbybSkydRyOtxwUPm4Y9qgaxVRiP5T.gamUktqH84r06x14hWgaEHnh03LWqlfpHnpGVPbi%2BMs%3D"},
    {"name": "__Secure-better-auth.session_data", "value": "eyJzZXNzaW9uIjp7InNlc3Npb24iOnsiZXhwaXJlc0F0IjoiMjAyNi0wNS0xNlQxOTozNjo1NS43MDlaIiwidG9rZW4iOiIwRWxieWJTa3lkUnlPdHh3VVBtNFk5cWdheFZSaVA1VCIsImNyZWF0ZWRBdCI6IjIwMjYtMDUtMDlUMTk6MzY6NTUuNzEwWiIsInVwZGF0ZWRBdCI6IjIwMjYtMDUtMDlUMTk6MzY6NTUuNzEwWiIsImlwQWRkcmVzcyI6IjIwMi40Ny4zNi40NCIsInVzZXJBZ2VudCI6Ik1vemlsbGEvNS4wIChXaW5kb3dzIE5UIDEwLjA7IFdpbjY0OyB4NjQpIEFwcGxlV2ViS2l0LzUzNy4zNiAoS0hUTUwsIGxpa2UgR2Vja28pIENocm9tZS8xNDcuMC4wLjAgU2FmYXJpLzUzNy4zNiIsInVzZXJJZCI6ImxpWXI3bkh4Y081VUtOU2FHOUp1QW1MbDI1QzZjSlhVIiwiaWQiOiI5NWFZaFJNVjRVQXc5V29uRjN2dkc3akpEcnd5SkdhYSJ9LCJ1c2VyIjp7Im5hbWUiOiJLaGFsaWQgSW1yYW4iLCJlbWFpbCI6InN0dWRlbnRodWIyMDI5QGdtYWlsLmNvbSIsImVtYWlsVmVyaWZpZWQiOnRydWUsImltYWdlIjpudWxsLCJjcmVhdGVkQXQiOiIyMDI2LTA1LTA5VDE5OjA3OjU5LjA3NFoiLCJ1cGRhdGVkQXQiOiIyMDI2LTA1LTA5VDE5OjA4OjE5Ljg0OVoiLCJpZCI6ImxpWXI3bkh4Y081VUtOU2FHOUp1QW1MbDI1QzZjSlhVIn0sInVwZGF0ZWRBdCI6MTc3ODM1NTQxNTgzNiwidmVyc2lvbiI6IjEifSwiZXhwaXJlc0F0IjoxNzc4MzU1NzE1ODM2LCJzaWduYXR1cmUiOiJQaVlla2FSNGhVTDFNclZOSlRmdWNTQUpQMmZ0Q3pLWHVMN2xnWXkyZkhRIn0"},
    {"name": "intercom-id-esc25l7u", "value": "6539bbfa-321c-4c19-aec6-52e0827442b1"},
]

data = json.dumps({"cookies": cookies}).encode()
req = urllib.request.Request(
    "http://localhost:8000/update-cookies",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req)
print("Done:", resp.read().decode())
