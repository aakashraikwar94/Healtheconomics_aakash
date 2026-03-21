"""
ASD Parent Sexual & Reproductive Health Chatbot
Flask backend — auth, chat history (SQLite), streaming Claude API responses.
"""

import os
import json
import functools
from flask import (
    Flask, render_template, request, Response,
    session, redirect, url_for, jsonify,
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import anthropic
from dotenv import load_dotenv

from database import (
    init_db, user_count, create_user, get_user_by_username, get_user_by_id,
    create_conversation, get_conversations, get_conversation,
    update_conversation_title, touch_conversation, delete_conversation,
    save_message, get_messages,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")
CORS(app)

# Initialise database on startup
with app.app_context():
    init_db()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a compassionate, knowledgeable health education specialist dedicated to helping parents and caregivers of autistic teenagers and adults understand sexual and reproductive health (SRH) topics. Your role is to provide evidence-based, practical, and sensitive guidance.

## Your Core Purpose
Help parents and caregivers of autistic individuals (teenagers and adults) to:
- Understand sexual development and reproductive health in the context of autism
- Learn how to communicate age-appropriate SRH information to their autistic child
- Navigate conversations about relationships, consent, boundaries, and bodily autonomy
- Access accurate information about contraception, STI prevention, and reproductive health services
- Address challenging behaviours related to sexuality in autism-affirming ways
- Understand the intersection of autism, sensory sensitivities, and sexual health
- Find professional support and community resources

## Key Principles
1. **Autism-Affirming**: Respect neurodiversity. Autistic people have the same rights to relationships, sexuality, and reproductive healthcare as anyone else.
2. **Inclusive Language**: Use person-first or identity-first language based on parent preference. Acknowledge the full spectrum of autism.
3. **Evidence-Based**: Provide information grounded in current research and best practices from organisations like SIECUS, AASECT, and autism advocacy groups.
4. **Non-Judgmental**: Create a safe, shame-free space. Parents may feel embarrassed or unsure — meet them with warmth.
5. **Culturally Sensitive**: Respect diverse cultural, religious, and family values while upholding the rights and safety of the autistic person.
6. **Safeguarding First**: Always prioritise the safety and wellbeing of the autistic individual. If abuse, exploitation, or harm is indicated, signpost to appropriate authorities and support services.

## Topics You Can Help With
- Puberty and body changes — explaining these to autistic teens
- Menstruation management and support
- Understanding and communicating consent
- Healthy vs unhealthy relationships
- Masturbation and privacy rules (teaching appropriate context)
- Contraception options and accessing services
- STI prevention and sexual health check-ups
- Pregnancy and reproductive choices
- LGBTQ+ identities and autism (co-occurrence is common)
- Online safety and digital relationships
- Sensory challenges and intimacy
- Protective behaviours programmes
- Challenging sexualised behaviours in autism-affirming ways
- Visual supports, social stories, and structured learning tools for SRH education
- How to find autism-aware sexual health professionals
- Legislation and rights around sexual health for people with disabilities

## Communication Style
- Use clear, plain language — avoid jargon
- Be warm, reassuring, and non-alarmist
- Normalise parents' questions; many parents feel isolated with these concerns
- When appropriate, suggest professional referrals (GP, clinical psychologist, autism specialist, RELATE counsellor, etc.)
- Recommend established resources (books, organisations, programmes) where relevant
- If a question is outside your expertise or requires clinical assessment, say so clearly and suggest professional help

## Boundaries
- You provide health education and parenting guidance — NOT clinical diagnosis or medical treatment advice
- For urgent safeguarding concerns, direct to local child/adult protection services immediately
- Do not provide explicit sexual content; maintain a health education framing at all times
- If asked about your identity, explain you are an AI health education assistant"""


# ── Auth helpers ───────────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def current_user():
    uid = session.get("user_id")
    return get_user_by_id(uid) if uid else None


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run setup — only accessible when no users exist."""
    if user_count() > 0:
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm  = request.form.get("confirm", "").strip()

        if not username or not password:
            error = "Username and password are required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            create_user(username, generate_password_hash(password))
            return redirect(url_for("login"))

    return render_template("setup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    # Redirect to setup if no accounts exist yet
    if user_count() == 0:
        return redirect(url_for("setup"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = get_user_by_username(username)

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        error = "Incorrect username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Main chat page ─────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"))


# ── Conversation API ───────────────────────────────────────────────────────────

@app.route("/api/conversations", methods=["GET"])
@login_required
def list_conversations():
    convs = get_conversations(session["user_id"])
    return jsonify(convs)


@app.route("/api/conversations", methods=["POST"])
@login_required
def new_conversation():
    conv_id = create_conversation(session["user_id"])
    return jsonify({"id": conv_id, "title": "New Conversation"})


@app.route("/api/conversations/<int:conv_id>", methods=["GET"])
@login_required
def load_conversation(conv_id):
    conv = get_conversation(conv_id, session["user_id"])
    if not conv:
        return jsonify({"error": "Not found"}), 404
    msgs = get_messages(conv_id)
    return jsonify({"conversation": conv, "messages": msgs})


@app.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
@login_required
def remove_conversation(conv_id):
    delete_conversation(conv_id, session["user_id"])
    return jsonify({"ok": True})


# ── Chat (streaming) ───────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
@login_required
def chat():
    data            = request.get_json()
    user_message    = data.get("message", "").strip()
    conv_id         = data.get("conversation_id")

    if not user_message:
        return Response(
            json.dumps({"error": "Message cannot be empty"}),
            status=400, mimetype="application/json",
        )

    user_id = session["user_id"]

    # Create a new conversation if none supplied
    if not conv_id:
        conv_id = create_conversation(user_id)

    # Verify ownership
    conv = get_conversation(conv_id, user_id)
    if not conv:
        return Response(
            json.dumps({"error": "Conversation not found"}),
            status=404, mimetype="application/json",
        )

    # Load history from DB
    history = get_messages(conv_id)
    messages = history + [{"role": "user", "content": user_message}]

    # Auto-title: use first user message (trimmed to 60 chars)
    is_first = len(history) == 0
    if is_first:
        title = user_message[:60] + ("…" if len(user_message) > 60 else "")
        update_conversation_title(conv_id, title)

    def generate():
        try:
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=messages,
                thinking={"type": "adaptive"},
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"

            final_message = stream.get_final_message()
            assistant_text = "".join(
                block.text for block in final_message.content if block.type == "text"
            )

            # Persist both turns
            save_message(conv_id, "user", user_message)
            save_message(conv_id, "assistant", assistant_text)
            touch_conversation(conv_id)

            yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id, 'assistant_message': assistant_text, 'is_first': is_first, 'title': title if is_first else conv['title']})}\n\n"

        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'Invalid API key. Please check your ANTHROPIC_API_KEY.'})}\n\n"
        except anthropic.RateLimitError:
            yield f"data: {json.dumps({'error': 'Rate limit reached. Please wait a moment and try again.'})}\n\n"
        except anthropic.APIError as e:
            yield f"data: {json.dumps({'error': f'API error: {str(e)}'})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/health")
def health():
    return {"status": "ok", "model": "claude-opus-4-6"}


if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
