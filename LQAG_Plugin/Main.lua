import "Turbine";
import "Turbine.Gameplay";

-- Setup
local player = Turbine.Gameplay.LocalPlayer.GetInstance();
local lastTargetName = "";

-- Ein unsichtbares Fenster erstellen, um das Update-Event zu nutzen (jeder Frame)
local scanner = Turbine.UI.Control();
scanner:SetWantsUpdates(true);

-- Funktion zum Speichern
function ExportTargetName(name)
    -- Wir speichern eine einfache Tabelle.
    -- LOTRO speichert dies als .plugindata Datei
    local data = {
        Target = name
    };
    
    -- Speichert unter "LQAG_Data.plugindata" für den ganzen Account
    Turbine.PluginData.Save(Turbine.DataScope.Account, "LQAG_Data", data);
    
    Turbine.Shell.WriteLine("<rgb=#FFFF00>[LQAG] Ziel erkannt: " .. name .. "</rgb>");
end

-- Der Loop (läuft ständig)
scanner.Update = function(sender, args)
    local target = player:GetTarget();
    
    if (target ~= nil) then
        local currentName = target:GetName();
        
        -- Nur speichern, wenn sich der Name geändert hat
        if (currentName ~= lastTargetName) then
            lastTargetName = currentName;
            ExportTargetName(currentName);
        end
    else
        -- Optional: Wenn kein Ziel, auf "None" setzen? 
        -- Besser nicht, sonst wechselt die Stimme ständig zurück.
        -- Wir behalten den letzten Sprecher bei.
    end
end

Turbine.Shell.WriteLine("<rgb=#00FF00>[LQAG] Reporter geladen. Wähle einen NPC an!</rgb>");