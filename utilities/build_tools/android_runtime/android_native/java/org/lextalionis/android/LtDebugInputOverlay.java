package org.lextalionis.android;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.text.InputType;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import java.nio.charset.StandardCharsets;

/**
 * Native Android editor for the in-game debugger.
 *
 * The pygame canvas remains responsible for the game and debugger drawer. This
 * class only adds one temporary view above that canvas while a manual value is
 * being edited. Python polls completed actions instead of receiving callbacks
 * on Android's UI thread.
 */
public final class LtDebugInputOverlay {
    private static final Object LOCK = new Object();
    private static final int MIN_TOUCH_TARGET_DP = 48;
    private static final int RAIL_WIDTH_DP = 56;
    private static final int SINGLE_LINE_HEIGHT_DP = 64;
    private static final int MULTILINE_MAX_HEIGHT_DP = 280;
    private static final int KEYBOARD_THRESHOLD_DP = 80;

    private static Activity activity;
    private static FrameLayout overlay;
    private static LinearLayout panel;
    private static DebugEditText editor;
    private static Button cancelButton;
    private static Button saveButton;
    private static ViewTreeObserver.OnGlobalLayoutListener layoutListener;
    private static String activeRequestId;
    private static String pendingResult;
    private static boolean multiline;
    private static boolean submitting;
    private static boolean keyboardVisible;

    private LtDebugInputOverlay() {
    }

    /** Show a native editor above the existing SDL activity. */
    public static boolean show(final Activity target, final String requestId,
                               final String initialValue, final boolean isMultiline,
                               final boolean numeric) {
        if (target == null || target.isFinishing() || requestId == null) {
            return false;
        }
        target.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                showOnUiThread(target, requestId, initialValue, isMultiline, numeric);
            }
        });
        return true;
    }

    /** Return one completed action as request-id, action, and base64 UTF-8 text. */
    public static String pollResult() {
        synchronized (LOCK) {
            String result = pendingResult;
            pendingResult = null;
            return result;
        }
    }

    /** Keep the current editor visible and surface a Python-side validation error. */
    public static void showError(final String requestId, final String message) {
        final Activity target;
        synchronized (LOCK) {
            if (requestId == null || !requestId.equals(activeRequestId) || activity == null) {
                return;
            }
            target = activity;
        }
        target.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                synchronized (LOCK) {
                    if (editor == null || !requestId.equals(activeRequestId)) {
                        return;
                    }
                    submitting = false;
                    setButtonsEnabled(true);
                    editor.setError(message == null ? "Invalid value" : message);
                    editor.requestFocus();
                    showKeyboard();
                }
            }
        });
    }

    /** Dismiss the active editor after Python accepts a value or changes state. */
    public static void dismiss(final String requestId) {
        final Activity target;
        synchronized (LOCK) {
            if (activity == null || (requestId != null && !requestId.equals(activeRequestId))) {
                return;
            }
            target = activity;
        }
        target.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                dismissOnUiThread();
            }
        });
    }

    /** Safe lifecycle cleanup for a debugger or activity that is closing. */
    public static void dismissAll() {
        final Activity target;
        synchronized (LOCK) {
            target = activity;
        }
        if (target != null) {
            target.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    dismissOnUiThread();
                }
            });
        }
    }

    private static void showOnUiThread(Activity target, String requestId, String initialValue,
                                       boolean isMultiline, boolean numeric) {
        dismissOnUiThread();
        activity = target;
        activeRequestId = requestId;
        multiline = isMultiline;
        submitting = false;
        keyboardVisible = false;
        synchronized (LOCK) {
            pendingResult = null;
        }

        overlay = new FrameLayout(target);
        overlay.setClickable(true);
        target.addContentView(overlay, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        panel = new LinearLayout(target);
        panel.setOrientation(LinearLayout.HORIZONTAL);
        panel.setGravity(Gravity.CENTER_VERTICAL);
        panel.setPadding(dp(target, 4), dp(target, 4), dp(target, 4), dp(target, 4));
        panel.setBackground(makeBackground(Color.rgb(250, 250, 250), Color.rgb(55, 95, 140), 1));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            panel.setElevation(dp(target, 6));
        }
        overlay.addView(panel, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(target, SINGLE_LINE_HEIGHT_DP),
                Gravity.TOP | Gravity.START));

        editor = new DebugEditText(target);
        editor.setTypeface(Typeface.DEFAULT);
        editor.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        editor.setTextColor(Color.rgb(27, 39, 54));
        editor.setGravity(isMultiline ? Gravity.TOP | Gravity.START : Gravity.CENTER_VERTICAL | Gravity.START);
        editor.setPadding(dp(target, 12), dp(target, 8), dp(target, 12), dp(target, 8));
        editor.setBackground(makeBackground(Color.WHITE, Color.rgb(99, 133, 170), 1));
        editor.setText(initialValue == null ? "" : initialValue);
        editor.setSelectAllOnFocus(false);
        editor.setSingleLine(!isMultiline);
        editor.setMaxLines(isMultiline ? Integer.MAX_VALUE : 1);
        editor.setHorizontallyScrolling(!isMultiline);
        editor.setImeOptions(isMultiline ? EditorInfo.IME_ACTION_NONE : EditorInfo.IME_ACTION_DONE);
        if (numeric) {
            editor.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_SIGNED);
        } else if (isMultiline) {
            editor.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                    | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        } else {
            editor.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        }
        editor.setOnEditorActionListener(new android.widget.TextView.OnEditorActionListener() {
            @Override
            public boolean onEditorAction(android.widget.TextView view, int actionId, KeyEvent event) {
                if (!multiline && (actionId == EditorInfo.IME_ACTION_DONE
                        || (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER))) {
                    emitResult("save");
                    return true;
                }
                return false;
            }
        });
        panel.addView(editor, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1.0f));

        LinearLayout rail = new LinearLayout(target);
        rail.setOrientation(LinearLayout.VERTICAL);
        rail.setGravity(Gravity.CENTER);
        panel.addView(rail, new LinearLayout.LayoutParams(
                dp(target, RAIL_WIDTH_DP), ViewGroup.LayoutParams.MATCH_PARENT));

        cancelButton = makeActionButton(target, "×", "Hủy chỉnh sửa", Color.rgb(106, 118, 133));
        cancelButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                emitResult("cancel");
            }
        });
        rail.addView(cancelButton, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.0f));

        saveButton = makeActionButton(target, "✓", "Lưu chỉnh sửa", Color.rgb(46, 112, 184));
        saveButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                emitResult("save");
            }
        });
        rail.addView(saveButton, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.0f));

        layoutListener = new ViewTreeObserver.OnGlobalLayoutListener() {
            @Override
            public void onGlobalLayout() {
                updatePanelBounds();
            }
        };
        overlay.getViewTreeObserver().addOnGlobalLayoutListener(layoutListener);
        overlay.post(new Runnable() {
            @Override
            public void run() {
                updatePanelBounds();
                if (editor != null) {
                    editor.requestFocus();
                    editor.setSelection(editor.length());
                    showKeyboard();
                }
            }
        });
    }

    private static Button makeActionButton(Context context, String label, String description, int color) {
        Button button = new Button(context);
        button.setText(label);
        button.setContentDescription(description);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        button.setTextColor(Color.WHITE);
        button.setAllCaps(false);
        button.setMinWidth(dp(context, MIN_TOUCH_TARGET_DP));
        button.setMinHeight(dp(context, MIN_TOUCH_TARGET_DP));
        button.setMinimumWidth(dp(context, MIN_TOUCH_TARGET_DP));
        button.setMinimumHeight(dp(context, MIN_TOUCH_TARGET_DP));
        button.setPadding(0, 0, 0, 0);
        button.setBackground(makeBackground(color, Color.TRANSPARENT, 0));
        return button;
    }

    private static GradientDrawable makeBackground(int color, int strokeColor, int strokeWidthDp) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(color);
        if (strokeWidthDp > 0 && activity != null) {
            background.setStroke(dp(activity, strokeWidthDp), strokeColor);
        }
        return background;
    }

    private static void updatePanelBounds() {
        if (overlay == null || panel == null || activity == null) {
            return;
        }
        Rect visibleFrame = new Rect();
        overlay.getWindowVisibleDisplayFrame(visibleFrame);
        int rootHeight = Math.max(1, overlay.getRootView().getHeight());
        int obscuredBottom = Math.max(0, rootHeight - visibleFrame.bottom);
        keyboardVisible = obscuredBottom >= dp(activity, KEYBOARD_THRESHOLD_DP);
        int visibleHeight = keyboardVisible ? Math.max(1, visibleFrame.bottom - visibleFrame.top) : rootHeight;
        int desiredHeight = multiline ? dp(activity, MULTILINE_MAX_HEIGHT_DP) : dp(activity, SINGLE_LINE_HEIGHT_DP);
        int panelHeight = Math.max(dp(activity, MIN_TOUCH_TARGET_DP), Math.min(desiredHeight, visibleHeight));
        FrameLayout.LayoutParams params = (FrameLayout.LayoutParams) panel.getLayoutParams();
        int leftInset = Math.max(0, visibleFrame.left);
        int rightInset = Math.max(0, overlay.getWidth() - visibleFrame.right);
        int topInset = Math.max(0, visibleFrame.top);
        if (params.height != panelHeight || params.topMargin != topInset
                || params.leftMargin != leftInset || params.rightMargin != rightInset) {
            params.height = panelHeight;
            params.leftMargin = leftInset;
            params.rightMargin = rightInset;
            params.topMargin = topInset;
            panel.setLayoutParams(params);
        }
    }

    private static void emitResult(String action) {
        final String requestId;
        final String value;
        synchronized (LOCK) {
            if (activeRequestId == null || editor == null || submitting) {
                return;
            }
            requestId = activeRequestId;
            value = editor.getText().toString();
            pendingResult = requestId + "\t" + action + "\t" + Base64.encodeToString(
                    value.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP);
            submitting = "save".equals(action);
            setButtonsEnabled(!submitting);
        }
        if ("cancel".equals(action)) {
            dismissOnUiThread();
        }
    }

    private static void setButtonsEnabled(boolean enabled) {
        if (cancelButton != null) {
            cancelButton.setEnabled(enabled);
        }
        if (saveButton != null) {
            saveButton.setEnabled(enabled);
        }
    }

    private static void showKeyboard() {
        if (editor == null || activity == null) {
            return;
        }
        InputMethodManager manager = (InputMethodManager) activity.getSystemService(Context.INPUT_METHOD_SERVICE);
        if (manager != null) {
            manager.showSoftInput(editor, InputMethodManager.SHOW_IMPLICIT);
        }
    }

    private static void hideKeyboard() {
        if (editor == null || activity == null) {
            return;
        }
        InputMethodManager manager = (InputMethodManager) activity.getSystemService(Context.INPUT_METHOD_SERVICE);
        if (manager != null) {
            manager.hideSoftInputFromWindow(editor.getWindowToken(), 0);
        }
    }

    private static void handleBackFromEditor() {
        if (keyboardVisible) {
            hideKeyboard();
        } else {
            emitResult("cancel");
        }
    }

    private static void dismissOnUiThread() {
        hideKeyboard();
        if (overlay != null && layoutListener != null
                && overlay.getViewTreeObserver().isAlive()) {
            overlay.getViewTreeObserver().removeOnGlobalLayoutListener(layoutListener);
        }
        if (overlay != null && overlay.getParent() instanceof ViewGroup) {
            ((ViewGroup) overlay.getParent()).removeView(overlay);
        }
        overlay = null;
        panel = null;
        editor = null;
        cancelButton = null;
        saveButton = null;
        layoutListener = null;
        activeRequestId = null;
        activity = null;
        submitting = false;
        keyboardVisible = false;
    }

    private static int dp(Context context, int value) {
        return Math.max(1, Math.round(value * context.getResources().getDisplayMetrics().density));
    }

    private static final class DebugEditText extends EditText {
        DebugEditText(Context context) {
            super(context);
        }

        @Override
        public boolean onKeyPreIme(int keyCode, KeyEvent event) {
            if (keyCode == KeyEvent.KEYCODE_BACK) {
                if (event.getAction() == KeyEvent.ACTION_UP) {
                    handleBackFromEditor();
                }
                return true;
            }
            return super.onKeyPreIme(keyCode, event);
        }
    }
}
