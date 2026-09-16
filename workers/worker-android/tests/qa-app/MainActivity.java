package org.example.telephonyqa;

import android.app.Activity;
import android.os.Bundle;
import android.telephony.TelephonyManager;
import android.telephony.SubscriptionManager;
import android.widget.TextView;
import org.json.JSONObject;

public class MainActivity extends Activity {
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        TextView view = new TextView(this);
        try {
            TelephonyManager tm = (TelephonyManager)getSystemService(TELEPHONY_SERVICE);
            SubscriptionManager sm = (SubscriptionManager)getSystemService(TELEPHONY_SUBSCRIPTION_SERVICE);
            JSONObject result = new JSONObject();
            result.put("imei", tm.getImei());
            result.put("imsi", tm.getSubscriberId());
            result.put("phone_number", tm.getLine1Number());
            result.put("subscription_number", sm.getPhoneNumber(1));
            result.put("operator", tm.getNetworkOperatorName());
            result.put("numeric", tm.getNetworkOperator());
            result.put("sim_operator", tm.getSimOperatorName());
            result.put("sim_numeric", tm.getSimOperator());
            result.put("country_iso", tm.getNetworkCountryIso());
            try (java.io.FileOutputStream stream = openFileOutput("telephony.json", MODE_PRIVATE)) {
                stream.write(result.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
            }
            view.setText(result.toString());
        } catch (Exception error) {
            view.setText(error.getClass().getSimpleName());
        }
        setContentView(view);
    }
}
