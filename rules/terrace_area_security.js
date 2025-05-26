/**
 * @name Terrace Area Security
 * @description Controls the surveillance camera and lighting based on the status of the terrace doors
 * @tags Windows, Camera, Security
 */

// Constants for better readability - using var instead of const for OpenHAB compatibility
var STATE_ON = "ON";
var STATE_OFF = "OFF";
var STATE_AUTO = "AUTO";
var STATE_OPEN = "OPEN";
var STATE_TILTED = "TILTED";
var STATE_RETRACT = "UP";

// Main rule function
(function() {
    try {
        console.debug("Terrace Area Security - Rule executed");
        
        // Output debug information
        console.debug(`backdoors_openstate: ${items.backdoors_openstate?.state || "not found"}`);
        
        if (items.backdoors_openstate?.state === STATE_ON) {
            console.debug("At least one door is not closed");
            
            if (items.window_livingright_handle && items.window_livingleft_handle) {
                var rightHandle = items.window_livingright_handle.state;
                var leftHandle = items.window_livingleft_handle.state;
                var doorOpen = rightHandle === STATE_OPEN || leftHandle === STATE_OPEN;
                var tilted = !doorOpen && (rightHandle === STATE_TILTED || leftHandle === STATE_TILTED);
                
                console.debug(`Status: Right door=${rightHandle}, Left door=${leftHandle}, Door open=${doorOpen}, Tilted=${tilted}`);
                
                if (tilted) {
                    console.debug("Activating security mode (door tilted)");
                    items.camera_terrace_monitoring?.sendCommandIfDifferent(STATE_ON);
                    items.camera_terrace_floodlight?.sendCommandIfDifferent(STATE_AUTO);
                    // Always send command as state reporting is unreliable
                    items.mainlamp_terrace_toggle?.sendCommand(STATE_OFF);
                    items.sunblinds_command?.sendCommand(STATE_RETRACT);
                } else {
                    console.debug("Deactivating surveillance (door open)");
                    items.camera_terrace_monitoring?.sendCommandIfDifferent(STATE_OFF);
                    items.camera_terrace_floodlight?.sendCommandIfDifferent(STATE_OFF);
                }
            } else {
                console.error("Error: Door handles not found");
            }
        } else {
            console.debug("All doors closed - Activating standard security mode");
            items.camera_terrace_monitoring?.sendCommandIfDifferent(STATE_ON);
            items.camera_terrace_floodlight?.sendCommandIfDifferent(STATE_AUTO);
            // Always send command as state reporting is unreliable
            items.mainlamp_terrace_toggle?.sendCommand(STATE_OFF);
            items.sunblinds_command?.sendCommand(STATE_RETRACT);
        }
    } catch (error) {
        console.error("Error in Terrace Area Security rule:", error);
    }
})();