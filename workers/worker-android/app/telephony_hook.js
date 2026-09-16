// QA fixture, deliberately scoped to the configured app's main process.
// No SMS/call interception, system property changes or native/Binder hooks.
rpc.exports = {
    install() {
        let installed = false;
        Java.performNow(function () {
            const tm = Java.use('android.telephony.TelephonyManager');
            const values = {
                getImei: fixture.imei,
                getDeviceId: fixture.imei,
                getSubscriberId: fixture.imsi,
                getLine1Number: fixture.phone_number,
                getNetworkOperatorName: fixture.operator,
                getSimOperatorName: fixture.operator,
                getNetworkOperator: fixture.mcc + fixture.mnc,
                getSimOperator: fixture.mcc + fixture.mnc,
                getNetworkCountryIso: fixture.country_iso,
                getSimCountryIso: fixture.country_iso
            };
            for (const [name, value] of Object.entries(values)) {
                for (const method of tm[name].overloads) {
                    method.implementation = function () { return value; };
                }
            }
            const sm = Java.use('android.telephony.SubscriptionManager');
            if (sm.getPhoneNumber) {
                for (const method of sm.getPhoneNumber.overloads) {
                    method.implementation = function () { return fixture.phone_number; };
                }
            }
            installed = true;
        });
        return installed;
    }
};
