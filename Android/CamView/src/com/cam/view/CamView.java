package com.cam.view;

import android.util.Log;
import android.os.Bundle;
import android.app.Activity;

import java.util.List;
import java.util.Arrays;

import android.content.Intent;
import android.content.Context;

import android.widget.Toast;
import android.widget.Button;
import android.widget.EditText;
import android.widget.RelativeLayout.LayoutParams;

import android.webkit.WebView;
import android.webkit.WebViewClient;

import android.view.View;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View.OnTouchListener;
import android.view.View.OnClickListener;

public class CamView extends Activity implements OnTouchListener {

  private WebView webView;

  private static Client client;

  private static Button button;
  private static EditText ipAddress;
  private static EditText camPortNumber;
  private static EditText serverPortNumber;
  private static DatabaseHandler db;

  private static String ipAddressDb;
  private static String camPortNumberDb;
  private static String serverPortNumberDb;

  private static String sIPAddress  = "";
  private static String sCamPortNumber = "";
  private static String sServerPortNumber = "";

  private static long backPressedTime = 0;

  @Override
  public void onBackPressed() {

    button.setVisibility(View.VISIBLE);

    long mTime = System.currentTimeMillis();
    if(mTime - backPressedTime > 2000) {
      backPressedTime = mTime;
      Toast.makeText(this, "Press back again to close app.", Toast.LENGTH_SHORT).show();
    }
    else {
      super.onBackPressed();
      Intent intent = new Intent(Intent.ACTION_MAIN);
      intent.addCategory(Intent.CATEGORY_HOME);
      startActivity(intent);
    }
  }

  @Override
  public void onResume() {
    super.onResume();
  }

  @Override
  public void onPause() {
    super.onPause();
  }

  public void onStop() {
    super.onStop();
  }

  @Override
  public void onDestroy() {
    super.onDestroy();
  } 

  @Override
  public void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    setContentView(R.layout.main);

    button     = (Button) findViewById(R.id.button);
    ipAddress  = (EditText) findViewById(R.id.editIPAddress);
    camPortNumber = (EditText) findViewById(R.id.editCamPort);
    serverPortNumber = (EditText) findViewById(R.id.editServerPort);

    db = new DatabaseHandler(CamView.this);
    getSetDatabaseInfo(0);

    //client = new Client(ipAddressDb, Integer.valueOf(portNumberDb), "start_monitor");  
    client = new Client(ipAddressDb, 50050, "start_monitor");  
    client.sendDataWithString();

    webView    = (WebView) findViewById(R.id.webView);

    webView.setVerticalScrollBarEnabled(false);
    webView.setHorizontalScrollBarEnabled(false);
    webView.setWebViewClient(new CamViewBrowser());
  
    String ip   = String.valueOf(ipAddressDb);
    String camPort = String.valueOf(camPortNumberDb);
    String serverPort = String.valueOf(serverPortNumberDb);
    final String addr = "http://" + ip + ":" + camPort + "/cam.mjpg";

    webView.loadUrl(addr);

    button.setOnClickListener(new OnClickListener() {
      @Override
      public void onClick(View v) {
        sanityCheck();
        String ip   = String.valueOf(sIPAddress);
        String camPort = String.valueOf(sCamPortNumber);
        String serverPort = String.valueOf(sServerPortNumber);
        String addr = "http://" + ip + ":" + camPort + "/cam.mjpg";

        //client = new Client(ipAddressDb, Integer.valueOf(portNumberDb), "start_monitor");  
        client = new Client(ipAddressDb, 50050, "start_monitor");  
        client.sendDataWithString();

        webView.setVerticalScrollBarEnabled(false);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setWebViewClient(new CamViewBrowser());
        webView.loadUrl(addr);
      }
    });

    serverPortNumber.setOnTouchListener(new OnTouchListener() {
      @Override
      public boolean onTouch(View v, MotionEvent event) {
        return false;
      }
    });

    ipAddress.setOnTouchListener(new OnTouchListener() {
      @Override
      public boolean onTouch(View v, MotionEvent event) {
        return false;
      }
    });

  }

  public void sanityCheck() {

    try {
      sIPAddress  = ipAddress.getText().toString();
      sCamPortNumber = camPortNumber.getText().toString();
      sServerPortNumber = serverPortNumber.getText().toString();
    }
    catch(Exception e) {
      e.printStackTrace();
      Log.e("CamView sanityCheck()", "getText() Error => " + e.getMessage(), e);
    }
    try {
      if(sIPAddress.isEmpty()) {
        Toast.makeText(this,"IP Address cannot be empty.", Toast.LENGTH_SHORT).show();
        return;
      }
      else if(sCamPortNumber.isEmpty()) {
        Toast.makeText(this,"Cam port Number cannot be empty.", Toast.LENGTH_SHORT).show();
        return;
      }
      else if(sServerPortNumber.isEmpty()) {
        Toast.makeText(this,"Server port Number cannot be empty.", Toast.LENGTH_SHORT).show();
        return;
      }
      else {
        getSetDatabaseInfo(1);
      }
    }
    catch(Exception e) {
      e.printStackTrace();
      Log.e("CamView sanityCheck()", "isEmpty() Error => " + e.getMessage(), e);
    }
  }

  public void getSetDatabaseInfo(int action) {

    List<Address> address = db.getAllAddresses();

    if(address == null) {
      return;
    }

    for(Address url : address) {
      ipAddressDb  = url.getIPAddress();
      camPortNumberDb = url.getCamPortNumber();
      serverPortNumberDb = url.getServerPortNumber();
    }

    switch(action) {
      case 0:
        if(ipAddressDb != null) {
          ipAddress.setText(ipAddressDb);
          serverPortNumber.setText(serverPortNumberDb);
        }
        break;
      case 1:
        if(ipAddressDb != null) {
          Log.d("CamView","getSetDatabaseInfo() case 1 - if ipAddressDb != null");
          db.updateAddress(new Address(1,sIPAddress,sCamPortNumber,sServerPortNumber));
        }
        else {
          Log.d("CamView","getSetDatabaseInfo() case 1 - else");
          db.addAddress(new Address(1,sIPAddress,sCamPortNumber,sServerPortNumber));
        }
        break;
    }

  }

  @Override
  public boolean onTouch(View v, MotionEvent event) {
    return false;
  }


  private class CamViewBrowser extends WebViewClient {
    @Override
    public boolean shouldOverrideUrlLoading(WebView view, String url) {
      view.loadUrl(url);
      return true;
    }
  }

}
