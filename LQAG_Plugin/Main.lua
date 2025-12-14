import "Turbine";
import "Turbine.Gameplay";
import "Turbine.UI";  -- <--- DAS HAT GEFEHLT!

local player = Turbine.Gameplay.LocalPlayer.GetInstance();
local lastTargetName = "";

-- Unsichtbares Fenster für Updates
local scanner = Turbine.UI.Control();
scanner:SetWantsUpdates(true);

scanner.Update = function(sender, args)
    local target = player:GetTarget();
    
    if (target ~= nil) then
        local currentName = target:GetName();
        
        if (currentName ~= lastTargetName) then
            lastTargetName = currentName;
            
            -- WICHTIG: print() schreibt in Script.log
            print(currentName);
            
            -- Optional: Nachricht im Chat für dich
            -- Turbine.Shell.WriteLine("Ziel erkannt: " .. currentName);
        end
    end
end

Turbine.Shell.WriteLine("LQAG Reporter bereit.");
