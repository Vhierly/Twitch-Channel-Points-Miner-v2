# Run this script in PowerShell as Administrator
# Setup port forwarding from Windows to WSL

$WSL_IP = (wsl hostname -I).Trim().Split()[0]
Write-Host "WSL IP: $WSL_IP"

# Remove old rules if exist
netsh interface portproxy delete v4tov4 listenport=5000 listenaddress=0.0.0.0 2>$null
netsh advfirewall firewall delete rule name="WSL Analytics 5000" 2>$null

# Add port forwarding
netsh interface portproxy add v4tov4 listenport=5000 listenaddress=0.0.0.0 connectport=5000 connectaddress=$WSL_IP

# Add firewall rule
netsh advfirewall firewall add rule name="WSL Analytics 5000" dir=in action=allow protocol=TCP localport=5000

Write-Host "Port forwarding setup complete!"
Write-Host "Access analytics at: http://localhost:5000"
Write-Host "Health check: http://localhost:5000/health"
Write-Host "Watch page: http://localhost:5000/watch"
