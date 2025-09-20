from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import StringField, TextAreaField, SelectField, RadioField, SubmitField, BooleanField, PasswordField, FileField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from datetime import datetime, timedelta
import os
import json
import uuid
from werkzeug.utils import secure_filename
import re
import markdown

# AI機能のためのインポート（オプション）
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    import torch
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("AI機能を使用するには transformers と torch をインストールしてください")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mentortrack.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 画像アップロード設定
UPLOAD_FOLDER = 'static/uploads/product_groups'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# アップロードフォルダを作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'ログインが必要です。'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# データベースモデル
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='mentee')  # mentee, mentor, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Mentee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    reports = db.relationship('WeeklyReport', backref='mentee', lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    todo_list = db.relationship('MenteeTodoList', backref='mentee', lazy=True, uselist=False)

class MenteeTodoList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey('mentee.id'), nullable=False)
    
    # 先輩社員の仕事を奪う
    senior_work_target = db.Column(db.String(200))  # 9月目標: 100SKU
    senior_work_actual = db.Column(db.String(200))  # 9月実績: _
    
    # 提案済みで発注済みの商品手配
    ordered_products = db.Column(db.String(200))  # ■912 ゲーミングモニター
    ordered_details = db.Column(db.Text)  # 発注済み 納期11/上、GM01 300、GM02 150
    
    # 提案済みでまだ発注できていない商品
    pending_products = db.Column(db.String(200))  # ■ビジネスリュック
    pending_details = db.Column(db.Text)  # 修正サンプル依頼→確認→発注(工藤さんに相談)、■775マットレス
    
    # 未提案の商品手配
    unproposed_products = db.Column(db.String(200))  # ■キャットタワー
    unproposed_details = db.Column(db.Text)  # 見積もり済み→構造修正9/24までに再見積もり依頼、■433転注フラッティ
    
    # 作成・更新日時
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WeeklyReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey('mentee.id'), nullable=False)
    
    # 企画ステージ
    planning_stage = db.Column(db.String(50), nullable=False)  # 提案前/提案済み/発注済み/完了
    
    # 代表商品群
    product_group = db.Column(db.Text, nullable=False)
    
    # 今週の進捗（JSON形式で保存）
    progress_items = db.Column(db.Text)  # チェックリスト項目
    
    # 実施した行動
    actions_taken = db.Column(db.Text)
    
    # 気づき・悩み
    insights_concerns = db.Column(db.Text)
    
    # 自己評価
    self_evaluation = db.Column(db.Integer)  # 1-3
    
    # 追加の問いかけ回答（JSON形式）
    additional_responses = db.Column(db.Text)
    
    # 報告日
    report_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 週の開始日（月曜日）
    week_start = db.Column(db.DateTime, nullable=False)
    
    # リレーションシップ
    mentor_comments = db.relationship('MentorComment', backref='report', lazy=True, cascade='all, delete-orphan')

class MentorComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('weekly_report.id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    mentor = db.relationship('User', backref='mentor_comments')

class DailyReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey('mentee.id'), nullable=False)
    weekly_report_id = db.Column(db.Integer, db.ForeignKey('weekly_report.id'), nullable=True)
    
    # 日報の基本情報
    report_date = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=False)  # 3行程度の要約
    
    # 生成された内容
    generated_content = db.Column(db.Text, nullable=False)  # AI生成された日報内容
    manual_edits = db.Column(db.Text)  # 手動で編集された内容
    
    # ステータス
    status = db.Column(db.String(20), default='draft')  # draft, published, archived
    
    # 作成・更新日時
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップ
    mentee = db.relationship('Mentee', backref='daily_reports')
    weekly_report = db.relationship('WeeklyReport', backref='daily_reports')

class ProductGroup(db.Model):
    """代表商品群マスタ"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    images = db.Column(db.Text)  # JSON形式で画像パスのリストを保存
    mentee_id = db.Column(db.Integer, db.ForeignKey('mentee.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップ
    mentee = db.relationship('Mentee', backref='product_groups')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'report_created', 'comment_added', 'system'
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 関連データのID（オプション）
    related_id = db.Column(db.Integer, nullable=True)  # 報告IDやコメントIDなど
    
    # リレーションシップ
    user = db.relationship('User', backref='notifications')

# フォームクラス
class RegistrationForm(FlaskForm):
    username = StringField('ユーザー名', 
                          validators=[DataRequired(), Length(min=2, max=20)],
                          render_kw={'placeholder': 'ユーザー名を入力してください'})
    email = StringField('メールアドレス', 
                       validators=[DataRequired(), Email()],
                       render_kw={'placeholder': 'メールアドレスを入力してください'})
    password = PasswordField('パスワード', 
                            validators=[DataRequired(), Length(min=6)],
                            render_kw={'placeholder': 'パスワードを入力してください'})
    confirm_password = PasswordField('パスワード確認', 
                                   validators=[DataRequired(), EqualTo('password')],
                                   render_kw={'placeholder': 'パスワードを再入力してください'})
    role = SelectField('役割', 
                      choices=[('mentee', 'メンティ'), ('mentor', 'メンター'), ('admin', '管理者')],
                      validators=[DataRequired()])
    submit = SubmitField('登録')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('そのユーザー名は既に使用されています。別のユーザー名を選択してください。')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('そのメールアドレスは既に登録されています。')

class LoginForm(FlaskForm):
    email = StringField('メールアドレス', 
                       validators=[DataRequired(), Email()],
                       render_kw={'placeholder': 'メールアドレスを入力してください'})
    password = PasswordField('パスワード', 
                            validators=[DataRequired()],
                            render_kw={'placeholder': 'パスワードを入力してください'})
    remember = BooleanField('ログイン状態を保持する')
    submit = SubmitField('ログイン')

class WeeklyReportForm(FlaskForm):
    planning_stage = SelectField('企画ステージ', 
                                choices=[('proposal_pre', '提案前'), 
                                        ('estimate_completed', '見積書対応'), 
                                        ('s_creation_approved', 'サンプル承認'), 
                                        ('proposal_decision_obtained', '提案決裁'),
                                        ('pre_production_s_confirmed', '量産前サンプル'),
                                        ('first_order', '初回発注'),
                                        ('temporary_listing', '仮出品'),
                                        ('page_up', 'ページアップ'),
                                        ('second_lot_ordered', '2ロット目発注'),
                                        ('project_cancelled', '企画中止')],
                                validators=[DataRequired()])
    
    product_group = SelectField('代表商品群', 
                               validators=[DataRequired()],
                               coerce=int,
                               render_kw={'placeholder': '商品群を選択してください'})
    
    def validate_product_group(self, field):
        if field.data == 0 or field.data is None:
            raise ValidationError('商品群を選択してください。')
        
        # 選択された商品群が存在するかチェック
        if field.data and field.data != 0:
            product_group = ProductGroup.query.get(field.data)
            if not product_group:
                raise ValidationError('選択された商品群が見つかりません。')
    
    # 進捗・行動統合フィールド
    progress_items = TextAreaField('今週の進捗・実施した行動', 
                                  render_kw={'rows': 6, 'placeholder': '今週の進捗状況と実施した具体的な行動を記述してください'})
    
    insights_concerns = TextAreaField('気づき・悩み', 
                                     render_kw={'rows': 4, 'placeholder': '今週感じた気づきや悩みを自由に記述してください'})
    
    self_evaluation = RadioField('自己評価', 
                                choices=[(1, '☆ - 思うように進まなかった'), 
                                        (2, '☆☆ - まあまあ進んだ'), 
                                        (3, '☆☆☆ - とても順調に進んだ')],
                                validators=[DataRequired()])
    
    # 追加の問いかけ
    time_consuming_task = TextAreaField('今週、最も時間を使った作業は？', 
                                       render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    difficult_decision = TextAreaField('今週、最も迷った判断は？', 
                                      render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    learned_from_senior = TextAreaField('今週、先輩から学んだことは？', 
                                       render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    own_decision = TextAreaField('今週、自分の判断で進めたことは？', 
                                render_kw={'rows': 2, 'placeholder': '（任意）'})
    
    
    submit = SubmitField('報告を保存')

class MentorCommentForm(FlaskForm):
    comment = TextAreaField('メンターコメント', 
                           validators=[DataRequired(), Length(min=1, max=1000)],
                           render_kw={'rows': 4, 'placeholder': 'メンターからのコメントを入力してください'})
    submit = SubmitField('コメントを保存')

class MenteeProfileForm(FlaskForm):
    name = StringField('メンティ名', 
                      validators=[DataRequired(), Length(min=1, max=100)],
                      render_kw={'placeholder': 'メンティ名を入力してください'})
    submit = SubmitField('プロファイルを更新')

class ProductGroupForm(FlaskForm):
    name = StringField('代表商品群名', 
                      validators=[DataRequired(), Length(min=1, max=10)],
                      render_kw={'placeholder': '代表商品群名を入力してください（最大10文字）'})
    description = TextAreaField('説明', 
                               render_kw={'rows': 3, 'placeholder': '商品群の説明（任意）'})
    images = FileField('画像ファイル', 
                      render_kw={'multiple': True, 'accept': 'image/*'})
    submit = SubmitField('登録')

class ProductGroupEditForm(FlaskForm):
    name = StringField('代表商品群名', 
                      validators=[DataRequired(), Length(min=1, max=10)],
                      render_kw={'placeholder': '代表商品群名を入力してください（最大10文字）'})
    description = TextAreaField('説明', 
                               render_kw={'rows': 3, 'placeholder': '商品群の説明（任意）'})
    images = FileField('新しい画像ファイル', 
                      render_kw={'multiple': True, 'accept': 'image/*'})
    submit = SubmitField('更新')

class DailyReportForm(FlaskForm):
    title = StringField('タイトル', 
                       validators=[DataRequired(), Length(min=1, max=200)],
                       render_kw={'placeholder': '日報のタイトルを入力してください'})
    summary = TextAreaField('要約（3行程度）', 
                           validators=[DataRequired(), Length(min=1, max=500)],
                           render_kw={'rows': 3, 'placeholder': '日報の要約を3行程度で入力してください'})
    content = TextAreaField('詳細内容', 
                           validators=[DataRequired()],
                           render_kw={'rows': 15, 'placeholder': '日報の詳細内容を入力してください'})
    submit = SubmitField('日報を保存')

# AI機能のクラス
class AIDailyReportGenerator:
    """AI機能を使った日報生成クラス"""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.is_initialized = False
        
        if AI_AVAILABLE:
            self.initialize_model()
    
    def initialize_model(self):
        """AIモデルを初期化"""
        try:
            # 軽量な日本語モデルを使用
            model_name = "rinna/japanese-gpt2-medium"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(model_name)
            self.is_initialized = True
            print("AI機能が初期化されました")
        except Exception as e:
            print(f"AI機能の初期化に失敗しました: {e}")
            self.is_initialized = False
    
    def generate_ai_summary(self, progress, actions, insights):
        """AIを使った要約生成"""
        if not self.is_initialized:
            return self.generate_fallback_summary(progress, actions, insights)
        
        try:
            prompt = f"""
            以下の週次報告データを基に、3行程度の要約を作成してください。
            
            進捗: {progress}
            実施した行動: {actions}
            気づき: {insights}
            
            要約:
            """
            
            inputs = self.tokenizer.encode(prompt, return_tensors="pt", max_length=512, truncation=True)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_length=inputs.shape[1] + 100,
                    num_return_sequences=1,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return self.extract_summary_from_ai_output(generated_text)
            
        except Exception as e:
            print(f"AI生成中にエラーが発生しました: {e}")
            return self.generate_fallback_summary(progress, actions, insights)
    
    def generate_fallback_summary(self, progress, actions, insights):
        """AIが使用できない場合のフォールバック要約"""
        return generate_ai_enhanced_summary(progress, actions, insights, "未評価")
    
    def extract_summary_from_ai_output(self, ai_output):
        """AI出力から要約を抽出"""
        # AI出力から要約部分を抽出
        lines = ai_output.split('\n')
        summary_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('進捗:') and not line.startswith('実施した行動:') and not line.startswith('気づき:'):
                summary_lines.append(line)
                if len(summary_lines) >= 3:
                    break
        
        return '\n'.join(summary_lines) if summary_lines else self.generate_fallback_summary("", "", "")

# グローバルAI生成器インスタンス
ai_generator = AIDailyReportGenerator()

# ヘルパー関数
def allowed_file(filename):
    """アップロード可能なファイルかチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_daily_report_from_weekly(weekly_report, report_date=None):
    """
    週次報告データから日報を自動生成する関数（品質重視版）
    """
    if report_date is None:
        report_date = datetime.now()
    
    # 週次報告のデータを取得
    mentee = weekly_report.mentee
    planning_stage = weekly_report.planning_stage
    product_group = weekly_report.product_group
    progress_items = weekly_report.progress_items or ""
    insights_concerns = weekly_report.insights_concerns or ""
    self_evaluation = weekly_report.self_evaluation
    
    # 追加の問いかけ回答を取得
    additional_responses = {}
    if weekly_report.additional_responses:
        try:
            additional_responses = eval(weekly_report.additional_responses)
        except:
            additional_responses = {}
    
    # 企画ステージの日本語名を取得（企画ステージフォームの表示形式に合わせる）
    stage_name = get_stage_display_name(planning_stage)
    
    # 自己評価の日本語名を取得
    evaluation_names = {
        1: '思うように進まなかった',
        2: 'まあまあ進んだ',
        3: 'とても順調に進んだ'
    }
    evaluation_name = evaluation_names.get(self_evaluation, '未評価')
    
    # 日報のタイトルを生成
    title = f"{report_date.strftime('%m月%d日')}の業務報告 - {product_group}"
    
    # 要約生成（元の文章を尊重）
    summary = generate_quality_summary(progress_items, insights_concerns, evaluation_name)
    
    # 詳細な日報内容を生成（元の文章を保持）
    content_parts = []
    
    # ヘッダー
    content_parts.append(f"# {title}")
    content_parts.append(f"**報告者**: {mentee.name}")
    content_parts.append(f"**報告日**: {report_date.strftime('%Y年%m月%d日')}")
    content_parts.append(f"**商品群**: {product_group}")
    content_parts.append(f"**現在のステージ**: {stage_name}")
    content_parts.append("")
    
    # 今週の進捗・実施した行動（統合版）
    if progress_items:
        content_parts.append("## 今週の進捗・実施した行動")
        content_parts.append(progress_items)
        content_parts.append("")
    
    # 気づき・悩み（元の文章を保持）
    if insights_concerns:
        content_parts.append("## 気づき・悩み")
        content_parts.append(insights_concerns)
        content_parts.append("")
    
    # 自己評価（自然な表現で生成）
    content_parts.append("## 自己評価")
    evaluation_text = generate_evaluation_text(evaluation_name, self_evaluation)
    content_parts.append(evaluation_text)
    content_parts.append("")
    
    # 追加の問いかけ回答（元の文章を保持）
    if additional_responses.get('time_consuming_task'):
        content_parts.append("## 今週の重点作業")
        content_parts.append(additional_responses['time_consuming_task'])
        content_parts.append("")
    
    if additional_responses.get('learned_from_senior'):
        content_parts.append("## 学んだこと")
        content_parts.append(additional_responses['learned_from_senior'])
        content_parts.append("")
    
    # 来週への展望（自然な表現で生成）
    content_parts.append("## 来週への展望")
    outlook_text = generate_outlook_text(planning_stage, product_group, insights_concerns)
    content_parts.append(outlook_text)
    
    generated_content = '\n'.join(content_parts)
    
    return {
        'title': title,
        'summary': summary,
        'generated_content': generated_content
    }

def generate_quality_summary(progress, insights, evaluation):
    """
    品質重視の要約を生成する関数（統合版）
    """
    summary_parts = []
    
    # 進捗・行動の要約（統合版）
    if progress:
        progress_lines = [line.strip() for line in progress.split('\n') if line.strip()]
        if progress_lines:
            summary_parts.append(f"【進捗・行動】{progress_lines[0]}")
    
    # 気づきや評価の要約（元の文章をそのまま使用）
    if insights:
        insight_lines = [line.strip() for line in insights.split('\n') if line.strip()]
        if insight_lines:
            summary_parts.append(f"【気づき】{insight_lines[0]}")
    else:
        summary_parts.append(f"【自己評価】{evaluation}")
    
    return '\n'.join(summary_parts[:3])

def generate_evaluation_text(evaluation_name, evaluation_score):
    """
    自己評価のテキストを自然に生成
    """
    if evaluation_score == 1:
        return f"今週は{evaluation_name}が、来週はより効率的に進められるよう改善を図ります。"
    elif evaluation_score == 2:
        return f"今週は{evaluation_name}が、来週はさらに成果を上げられるよう取り組みます。"
    elif evaluation_score == 3:
        return f"今週は{evaluation_name}が、この調子で来週も継続していきます。"
    else:
        return f"今週の自己評価は{evaluation_name}です。"

def generate_outlook_text(planning_stage, product_group, insights):
    """
    来週への展望を自然に生成
    """
    outlook_templates = {
        'second_lot_ordered': f"{product_group}の企画が完了しました。次の商品群の企画に取り組み、さらなる成長を目指します。",
        'page_up': f"{product_group}の販売開始に向けて、マーケティング活動を強化し、売上向上に努めます。",
        'first_order': f"{product_group}の初回発注を完了し、品質管理と販売準備を進めます。",
        'temporary_listing': f"{product_group}の仮出品に向けて、商品の品質確認と発注準備を着実に進めます。",
        'pre_production_s_confirmed': f"{product_group}の量産前確認を完了し、次のステップに向けた準備を進めます。",
        'proposal_decision_obtained': f"{product_group}の提案決裁を取得し、量産準備に取り組みます。",
        's_creation_approved': f"{product_group}のサンプル承認を取得し、提案決裁に向けて進めます。",
        'estimate_completed': f"{product_group}の見積書対応を完了し、サンプル承認に向けて進めます。",
        'proposal_pre': f"{product_group}の企画を進め、見積書対応に向けて準備を進めます。",
        'project_cancelled': f"{product_group}の企画は中止となりました。他の商品群の企画に集中し、新たな機会を探ります。"
    }
    
    base_outlook = outlook_templates.get(planning_stage, f"{product_group}の企画を進め、次のステップに向けて準備を進めます。")
    
    # 気づきに基づく追加の展望
    if insights:
        insight_lines = [line.strip() for line in insights.split('\n') if line.strip()]
        if insight_lines:
            base_outlook += f" また、今週の気づき「{insight_lines[0]}」を活かして、より効果的な取り組みを心がけます。"
    
    return base_outlook

def get_product_group_latest_stages(mentee_id):
    """
    商品群ごとの最新の進捗ステージを取得
    """
    # メンティの商品群を取得
    product_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).all()
    product_group_stages = {}
    
    for pg in product_groups:
        # 各商品群の最新の週次報告を取得
        latest_report = WeeklyReport.query.filter_by(
            mentee_id=mentee_id,
            product_group=pg.name
        ).order_by(WeeklyReport.report_date.desc()).first()
        
        if latest_report:
            # ステージの日本語名を取得（企画ステージフォームの表示形式に合わせる）
            product_group_stages[pg.id] = {
                'name': pg.name,
                'latest_stage': latest_report.planning_stage,
                'latest_stage_name': get_stage_display_name(latest_report.planning_stage),
                'last_report_date': latest_report.report_date.strftime('%Y年%m月%d日'),
                'has_reports': True
            }
        else:
            product_group_stages[pg.id] = {
                'name': pg.name,
                'latest_stage': None,
                'latest_stage_name': '未報告',
                'last_report_date': None,
                'has_reports': False
            }
    
    return product_group_stages

def generate_ai_enhanced_summary(progress, insights, evaluation):
    """
    AI風の要約を生成する関数（レガシー）
    """
    return generate_quality_summary(progress, insights, evaluation)

def enhance_progress_description(progress_text):
    """
    進捗記述をより自然な表現に変換（改善版）
    """
    # 元の文章を保持し、最小限の改善のみ行う
    enhanced_text = progress_text.strip()
    
    # 文末の調整のみ（重複を避ける）
    if not enhanced_text.endswith(('。', 'ました', 'ています', 'です', 'です。', 'ました。')):
        enhanced_text += '。'
    
    return enhanced_text

def enhance_actions_description(actions_text):
    """
    実施した行動の記述をより自然な表現に変換（改善版）
    """
    # 元の文章を保持し、最小限の改善のみ行う
    enhanced_text = actions_text.strip()
    
    # 文末の調整のみ（重複を避ける）
    if not enhanced_text.endswith(('。', 'ました', 'ています', 'です', 'です。', 'ました。')):
        enhanced_text += '。'
    
    return enhanced_text

def enhance_insights_description(insights_text):
    """
    気づき・悩みの記述をより自然な表現に変換（改善版）
    """
    # 元の文章を保持し、最小限の改善のみ行う
    enhanced_text = insights_text.strip()
    
    # 文末の調整のみ（重複を避ける）
    if not enhanced_text.endswith(('。', 'ました', 'ています', 'です', 'です。', 'ました。')):
        enhanced_text += '。'
    
    return enhanced_text

def enhance_evaluation_description(evaluation_name, evaluation_score):
    """
    自己評価の記述をより自然な表現に変換（改善版）
    """
    if evaluation_score == 1:
        return f"今週は{evaluation_name}が、来週はより効率的に進められるよう改善を図ります。"
    elif evaluation_score == 2:
        return f"今週は{evaluation_name}が、来週はさらに成果を上げられるよう取り組みます。"
    elif evaluation_score == 3:
        return f"今週は{evaluation_name}が、この調子で来週も継続していきます。"
    else:
        return f"今週の自己評価は{evaluation_name}です。"

def enhance_task_description(task_text):
    """
    重点作業の記述をより自然な表現に変換（改善版）
    """
    enhanced_text = task_text.strip()
    if not enhanced_text.endswith(('。', 'ました', 'ています', 'です', 'です。', 'ました。')):
        enhanced_text += '。'
    return enhanced_text

def enhance_learning_description(learning_text):
    """
    学んだことの記述をより自然な表現に変換（改善版）
    """
    enhanced_text = learning_text.strip()
    if not enhanced_text.endswith(('。', 'ました', 'ています', 'です', 'です。', 'ました。')):
        enhanced_text += '。'
    return enhanced_text

def generate_enhanced_outlook(planning_stage, product_group, insights):
    """
    来週への展望をより自然で具体的な表現で生成
    """
    outlook_templates = {
        'second_lot_ordered': f"{product_group}の企画が完了しました。次の商品群の企画に取り組み、さらなる成長を目指します。",
        'page_up': f"{product_group}の販売開始に向けて、マーケティング活動を強化し、売上向上に努めます。",
        'first_order': f"{product_group}の初回発注を完了し、品質管理と販売準備を進めます。",
        'temporary_listing': f"{product_group}の仮出品に向けて、商品の品質確認と発注準備を着実に進めます。",
        'pre_production_s_confirmed': f"{product_group}の量産前確認を完了し、次のステップに向けた準備を進めます。",
        'proposal_decision_obtained': f"{product_group}の提案決裁を取得し、量産準備に取り組みます。",
        's_creation_approved': f"{product_group}のサンプル承認を取得し、提案決裁に向けて進めます。",
        'estimate_completed': f"{product_group}の見積書対応を完了し、サンプル承認に向けて進めます。",
        'proposal_pre': f"{product_group}の企画を進め、見積書対応に向けて準備を進めます。",
        'project_cancelled': f"{product_group}の企画は中止となりました。他の商品群の企画に集中し、新たな機会を探ります。"
    }
    
    base_outlook = outlook_templates.get(planning_stage, f"{product_group}の企画を進め、次のステップに向けて準備を進めます。")
    
    # 気づきに基づく追加の展望
    if insights:
        insight_lines = [line.strip() for line in insights.split('\n') if line.strip()]
        if insight_lines:
            base_outlook += f" また、今週の気づき「{insight_lines[0]}」を活かして、より効果的な取り組みを心がけます。"
    
    return base_outlook

def save_uploaded_files(files):
    """アップロードされたファイルを保存"""
    saved_files = []
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            # ユニークなファイル名を生成
            filename = secure_filename(file.filename)
            name, ext = os.path.splitext(filename)
            unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            
            # ファイルを保存
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            saved_files.append(unique_filename)
    
    return saved_files

def delete_uploaded_files(filenames):
    """アップロードされたファイルを削除"""
    for filename in filenames:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)

def create_notification(user_id, title, message, notification_type, related_id=None):
    """通知を作成する"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        related_id=related_id
    )
    db.session.add(notification)
    db.session.commit()
    return notification

def get_product_group_progress(mentee_id, weeks=16):
    """商品群別の進捗状況を取得（4か月=16週間の開発期間を想定）"""
    from datetime import datetime, timedelta
    
    # 現在存在する商品群のリストを取得
    existing_product_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).all()
    existing_product_group_names = {pg.name for pg in existing_product_groups}
    
    
    # 4か月分の過去の報告を取得
    end_date = datetime.now()
    start_date = end_date - timedelta(weeks=weeks)
    
    reports = WeeklyReport.query.filter(
        WeeklyReport.mentee_id == mentee_id,
        WeeklyReport.report_date >= start_date
    ).order_by(WeeklyReport.report_date.desc()).all()
    
    # 商品群ごとに進捗を整理
    product_groups = {}
    
    for report in reports:
        product_group_name = report.product_group
        
        # 商品群が削除されている場合は進捗サマリーに表示しない
        if product_group_name not in existing_product_group_names:
            continue
        
        if product_group_name not in product_groups:
            # ProductGroupモデルから画像情報を取得
            product_group = ProductGroup.query.filter_by(
                name=product_group_name, 
                mentee_id=mentee_id
            ).first()
            
            product_groups[product_group_name] = {
                'id': product_group.id if product_group else None,
                'name': product_group_name,
                'images': product_group.images if product_group else None,
                'reports': [],
                'current_stage': None,
                'stage_duration': 0,
                'progress_status': 'unknown',
                'is_completed': False,
                'created_at': product_group.created_at if product_group else None,
                'stage': None
            }
        
        product_groups[product_group_name]['reports'].append({
            'id': report.id,
            'date': report.report_date,
            'stage': report.planning_stage,
            'self_evaluation': report.self_evaluation
        })
        
        # 最新のステージを設定
        if not product_groups[product_group_name]['stage']:
            product_groups[product_group_name]['stage'] = report.planning_stage
    
    # 各商品群の進捗状況を分析
    for pg_name, pg_data in product_groups.items():
        if pg_data['reports']:
            # 最新の報告のステージを現在のステージとする
            latest_report = pg_data['reports'][0]
            pg_data['current_stage'] = latest_report['stage']
            
            # 完了ステージかどうかを判定
            pg_data['is_completed'] = latest_report['stage'] == 'second_lot_ordered'
            
            # 企画中止かどうかを判定
            pg_data['is_cancelled'] = latest_report['stage'] == 'project_cancelled'
            
            # 現在のステージにいる期間を計算
            current_stage_start = latest_report['date']
            for report in pg_data['reports']:
                if report['stage'] != latest_report['stage']:
                    current_stage_start = report['date']
                    break
            
            days_in_stage = (datetime.now() - current_stage_start).days
            pg_data['stage_duration'] = days_in_stage
            
            # 最後の報告からの期間を計算
            days_since_last_report = (datetime.now() - latest_report['date']).days
            
            # 初回登録時からの経過週数で警告レベルを判定（4週間ごとに段階的変化）
            if pg_data['reports']:
                # 最初の報告日を初回登録日とする
                first_report_date = min(report['date'] for report in pg_data['reports'])
                weeks_since_start = (datetime.now() - first_report_date).days // 7
            else:
                weeks_since_start = 0
            
            # 経過週数をデータに追加
            pg_data['weeks_since_start'] = weeks_since_start
            
            # 完了済みの場合は警告なし
            if pg_data['is_completed']:
                pg_data['progress_status'] = 'completed'
                pg_data['time_warning_level'] = 0
            elif pg_data['is_cancelled']:
                # 企画中止の場合は専用の状況
                pg_data['progress_status'] = 'cancelled'
                pg_data['time_warning_level'] = 0
            else:
                # 4週間ごとに段階的に警告レベルを上げる
                if weeks_since_start < 4:
                    # 0-3週間：緑（正常）
                    pg_data['progress_status'] = 'good'
                    pg_data['time_warning_level'] = 0
                elif weeks_since_start < 8:
                    # 4-7週間：黄色（軽度警告）
                    pg_data['progress_status'] = 'warning'
                    pg_data['time_warning_level'] = 1
                elif weeks_since_start < 12:
                    # 8-11週間：オレンジ（中程度警告）
                    pg_data['progress_status'] = 'warning'
                    pg_data['time_warning_level'] = 2
                elif weeks_since_start < 16:
                    # 12-15週間：赤（高度警告）
                    pg_data['progress_status'] = 'danger'
                    pg_data['time_warning_level'] = 3
                else:
                    # 16週間以上：濃い赤（最高度警告）
                    pg_data['progress_status'] = 'danger'
                    pg_data['time_warning_level'] = 4
    
    return list(product_groups.values())

def get_stage_display_name(stage):
    """企画ステージの表示名を取得（統一された表示形式）"""
    stage_names = {
        'proposal_pre': '提案前',
        'estimate_completed': '見積書対応',
        's_creation_approved': 'サンプル承認',
        'proposal_decision_obtained': '提案決裁',
        'pre_production_s_confirmed': '量産前サンプル',
        'first_order': '初回発注',
        'temporary_listing': '仮出品',
        'page_up': 'ページアップ',
        'second_lot_ordered': '2ロット目発注',
        'project_cancelled': '企画中止'
    }
    return stage_names.get(stage, stage)

def render_markdown(text):
    """マークダウンテキストをHTMLに変換する"""
    if not text:
        return ""
    try:
        # デバッグ用ログ
        print(f"Rendering markdown text: {text[:100]}...")
        
        # マークダウンをHTMLに変換
        html = markdown.markdown(text, extensions=['extra', 'codehilite', 'tables'])
        
        # デバッグ用ログ
        print(f"Rendered HTML: {html[:100]}...")
        
        return html
    except Exception as e:
        # エラーが発生した場合は元のテキストを返す
        print(f"Markdown rendering error: {e}")
        return text.replace('\n', '<br>')

def get_stage_progress_percentage(stage):
    """企画ステージの進捗パーセンテージを取得"""
    stage_percentages = {
        'proposal_pre': 11,
        'estimate_completed': 22,
        's_creation_approved': 33,
        'proposal_decision_obtained': 44,
        'pre_production_s_confirmed': 56,
        'first_order': 67,
        'temporary_listing': 78,
        'page_up': 89,
        'second_lot_ordered': 100,
        'project_cancelled': 100
    }
    return stage_percentages.get(stage, 0)

def get_progress_status_info(status):
    """進捗状況の表示情報を取得"""
    status_info = {
        'good': {'class': 'success', 'icon': 'fas fa-arrow-up', 'text': '順調'},
        'warning': {'class': 'warning', 'icon': 'fas fa-pause', 'text': '注意'},
        'danger': {'class': 'danger', 'icon': 'fas fa-exclamation-triangle', 'text': '停滞'},
        'completed': {'class': 'success', 'icon': 'fas fa-check-circle', 'text': '完了'},
        'cancelled': {'class': 'secondary', 'icon': 'fas fa-ban', 'text': '企画中止'},
        'unknown': {'class': 'secondary', 'icon': 'fas fa-question', 'text': '不明'}
    }
    return status_info.get(status, status_info['unknown'])

# カスタムフィルター
@app.template_filter('from_json')
def from_json_filter(json_string):
    """JSON文字列をPythonオブジェクトに変換するフィルター"""
    if not json_string:
        return []
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return []

# テンプレートコンテキストプロセッサー
@app.context_processor
def utility_processor():
    return dict(
        get_stage_display_name=get_stage_display_name,
        get_stage_progress_percentage=get_stage_progress_percentage,
        get_progress_status_info=get_progress_status_info,
        render_markdown=render_markdown
    )

# ルート
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/my-dashboard')
@login_required
def my_dashboard():
    """ログインユーザーに応じたダッシュボードにリダイレクト"""
    if current_user.role == 'mentee':
        # メンティの場合、自分のメンティレコードを取得
        mentee = Mentee.query.filter_by(user_id=current_user.id).first()
        if mentee:
            return redirect(url_for('mentee_dashboard', mentee_id=mentee.id))
        else:
            # メンティレコードが存在しない場合は作成
            try:
                mentee = Mentee(
                    name=current_user.username,
                    email=current_user.email,
                    user_id=current_user.id
                )
                db.session.add(mentee)
                db.session.commit()
                flash('メンティプロファイルが作成されました。', 'success')
                return redirect(url_for('mentee_dashboard', mentee_id=mentee.id))
            except Exception as e:
                flash(f'メンティプロファイルの作成に失敗しました: {str(e)}', 'danger')
                return redirect(url_for('index'))
    elif current_user.role == 'mentor':
        return redirect(url_for('mentor_dashboard'))
    elif current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        flash('不明な役割です。', 'danger')
        return redirect(url_for('index'))

@app.route('/debug/mentees')
@login_required
def debug_mentees():
    """デバッグ用：メンティ一覧を表示"""
    if current_user.role not in ['admin']:
        flash('管理者権限が必要です。', 'danger')
        return redirect(url_for('index'))
    
    mentees = Mentee.query.all()
    debug_info = []
    for mentee in mentees:
        debug_info.append({
            'id': mentee.id,
            'name': mentee.name,
            'email': mentee.email,
            'user_id': mentee.user_id,
            'created_at': mentee.created_at
        })
    
    return jsonify({
        'mentees': debug_info,
        'current_user': {
            'id': current_user.id,
            'username': current_user.username,
            'role': current_user.role
        }
    })

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # ユーザーIDを取得するためにflush
        
        # メンティの場合、メンティレコードも作成
        if form.role.data == 'mentee':
            mentee = Mentee(
                name=form.username.data,  # 初期値としてユーザー名を使用
                email=form.email.data,
                user_id=user.id
            )
            db.session.add(mentee)
        
        db.session.commit()
        flash('アカウントが作成されました！ログインしてください。', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        print(f"ログイン試行: メール={form.email.data}")
        user = User.query.filter_by(email=form.email.data).first()
        print(f"ユーザーが見つかった: {user is not None}")
        if user:
            print(f"ユーザー名: {user.username}")
            print(f"パスワードハッシュ: {user.password_hash[:50]}...")
            password_check = user.check_password(form.password.data)
            print(f"パスワードチェック結果: {password_check}")
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'ようこそ、{user.username}さん！', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('ログインに失敗しました。メールアドレスとパスワードを確認してください。', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('index'))

@app.route('/mentee/<int:mentee_id>')
@login_required
def mentee_dashboard(mentee_id):
    mentee = Mentee.query.get_or_404(mentee_id)
    
    # セキュリティチェック：メンティは自分の報告のみ、メンター・管理者は全報告を閲覧可能
    if current_user.role == 'mentee':
        # メンティの場合、自分のメンティレコードのみアクセス可能
        if mentee.user_id != current_user.id:
            flash('アクセス権限がありません。', 'danger')
            return redirect(url_for('my_dashboard'))
    
    reports = WeeklyReport.query.filter_by(mentee_id=mentee_id).order_by(WeeklyReport.report_date.desc()).all()
    
    # 商品群別進捗データを取得
    product_group_progress = get_product_group_progress(mentee_id)
    
    return render_template('mentee_dashboard.html', 
                         mentee=mentee, 
                         reports=reports, 
                         product_group_progress=product_group_progress)

@app.route('/mentor/dashboard')
@login_required
def mentor_dashboard():
    # メンター権限チェック
    if current_user.role not in ['mentor', 'admin']:
        flash('メンター権限が必要です。', 'danger')
        return redirect(url_for('index'))
    
    # フィルターパラメータを取得
    mentee_filter = request.args.get('mentee', '')
    
    # 全メンティの報告を取得（フィルター適用）
    query = WeeklyReport.query.join(Mentee)
    
    if mentee_filter:
        query = query.filter(Mentee.name.contains(mentee_filter))
    
    reports = query.order_by(WeeklyReport.report_date.desc()).all()
    
    # メンティ一覧を取得（フィルター用）
    mentees = Mentee.query.order_by(Mentee.name).all()
    
    # 商品群別進捗データを取得
    product_group_progress = []
    if mentee_filter:
        # 特定のメンティの進捗データ
        selected_mentee = Mentee.query.filter(Mentee.name.contains(mentee_filter)).first()
        if selected_mentee:
            product_group_progress = get_product_group_progress(selected_mentee.id)
    else:
        # 全メンティの進捗データ
        for mentee in mentees:
            mentee_progress = get_product_group_progress(mentee.id)
            for pg in mentee_progress:
                pg['mentee_name'] = mentee.name
            product_group_progress.extend(mentee_progress)
    
    # メンティデータを辞書形式に変換（JavaScript用）
    mentees_data = [{'id': mentee.id, 'name': mentee.name} for mentee in mentees]
    
    return render_template('mentor_dashboard.html', 
                         reports=reports, 
                         mentees=mentees_data, 
                         selected_mentee=mentee_filter,
                         product_group_progress=product_group_progress)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """管理者用ダッシュボード"""
    if current_user.role != 'admin':
        flash('管理者権限が必要です。', 'danger')
        return redirect(url_for('index'))
    
    # システム統計情報を取得
    total_users = User.query.count()
    total_mentees = Mentee.query.count()
    total_reports = WeeklyReport.query.count()
    total_comments = MentorComment.query.count()
    
    # 最近の活動
    recent_reports = WeeklyReport.query.order_by(WeeklyReport.report_date.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # ユーザー統計
    users_by_role = db.session.query(User.role, db.func.count(User.id)).group_by(User.role).all()
    
    return render_template('admin_dashboard.html', 
                         total_users=total_users,
                         total_mentees=total_mentees,
                         total_reports=total_reports,
                         total_comments=total_comments,
                         recent_reports=recent_reports,
                         recent_users=recent_users,
                         users_by_role=users_by_role)

@app.route('/admin/users')
@login_required
def admin_users():
    """ユーザー管理画面"""
    if current_user.role != 'admin':
        flash('管理者権限が必要です。', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    """ユーザー削除"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': '管理者権限が必要です。'}), 403
    
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': '自分自身を削除することはできません。'}), 400
    
    try:
        user = User.query.get_or_404(user_id)
        
        # 関連するメンティレコードも削除
        mentee = Mentee.query.filter_by(user_id=user_id).first()
        if mentee:
            # メンティの報告も削除
            WeeklyReport.query.filter_by(mentee_id=mentee.id).delete()
            db.session.delete(mentee)
        
        # メンターコメントも削除
        MentorComment.query.filter_by(mentor_id=user_id).delete()
        
        # ユーザーを削除
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'ユーザーが削除されました。'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'エラーが発生しました: {str(e)}'}), 500

@app.route('/admin/mentees')
@login_required
def admin_mentees():
    """メンティ管理画面"""
    if current_user.role != 'admin':
        flash('管理者権限が必要です。', 'danger')
        return redirect(url_for('index'))
    
    mentees = Mentee.query.order_by(Mentee.created_at.desc()).all()
    return render_template('admin_mentees.html', mentees=mentees)

@app.route('/admin/mentees/<int:mentee_id>/delete', methods=['POST'])
@login_required
def admin_delete_mentee(mentee_id):
    """メンティ削除"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': '管理者権限が必要です。'}), 403
    
    try:
        mentee = Mentee.query.get_or_404(mentee_id)
        
        # 関連する報告を削除
        WeeklyReport.query.filter_by(mentee_id=mentee_id).delete()
        
        # メンティを削除
        db.session.delete(mentee)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'メンティが削除されました。'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'エラーが発生しました: {str(e)}'}), 500

@app.route('/report/new/<int:mentee_id>', methods=['GET', 'POST'])
@login_required
def new_report(mentee_id):
    try:
        # メンティの存在確認
        mentee = Mentee.query.get(mentee_id)
        if not mentee:
            flash(f'メンティID {mentee_id} が見つかりません。', 'danger')
            return redirect(url_for('my_dashboard'))
        
        # セキュリティチェック：メンティは自分の報告のみ作成可能
        if current_user.role == 'mentee':
            if mentee.user_id != current_user.id:
                flash(f'アクセス権限がありません。メンティID {mentee_id} はあなたのものではありません。', 'danger')
                return redirect(url_for('my_dashboard'))
        
        form = WeeklyReportForm()
        
        # 代表商品群の選択肢を動的に設定
        product_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).all()
        form.product_group.choices = [(0, '商品群を選択してください')] + [(pg.id, pg.name) for pg in product_groups]
        
        # 代表商品群が登録されていない場合の警告
        if not product_groups:
            flash('代表商品群が登録されていません。先に代表商品群を登録してください。', 'warning')
        
        # Todoリストを取得（存在しない場合は作成）
        todo_list = MenteeTodoList.query.filter_by(mentee_id=mentee_id).first()
        if not todo_list:
            todo_list = MenteeTodoList(mentee_id=mentee_id)
            db.session.add(todo_list)
            db.session.commit()
        
        # デバッグ用：Todoリストの内容を確認
        print(f"DEBUG: Todoリスト取得 - mentee_id: {mentee_id}")
        print(f"DEBUG: Todoリスト内容: {todo_list}")
        if todo_list:
            print(f"DEBUG: senior_work_target: {todo_list.senior_work_target}")
            print(f"DEBUG: ordered_products: {todo_list.ordered_products}")
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('my_dashboard'))
    
    if form.validate_on_submit():
        try:
            # 今週の月曜日を計算
            today = datetime.now()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 追加の問いかけ回答をJSON形式で保存
            additional_responses = {
                'time_consuming_task': form.time_consuming_task.data,
                'difficult_decision': form.difficult_decision.data,
                'learned_from_senior': form.learned_from_senior.data,
                'own_decision': form.own_decision.data
            }
            
            # 選択された代表商品群の名前を取得
            selected_product_group = ProductGroup.query.get(form.product_group.data)
            if not selected_product_group:
                flash('選択された商品群が見つかりません。商品群を再選択してください。', 'danger')
                product_group_stages = get_product_group_latest_stages(mentee_id)
                return render_template('new_report.html', form=form, mentee=mentee, todo_list=todo_list, product_groups=product_groups, product_group_stages=product_group_stages)
            
            product_group_name = selected_product_group.name
            
            report = WeeklyReport(
                mentee_id=mentee_id,
                planning_stage=form.planning_stage.data,
                product_group=product_group_name,
                progress_items=form.progress_items.data,
                actions_taken="",  # 統合により空文字列に設定
                insights_concerns=form.insights_concerns.data,
                self_evaluation=form.self_evaluation.data,
                additional_responses=str(additional_responses),
                week_start=week_start
            )
            
            db.session.add(report)
            db.session.commit()
            
            # メンターに通知を送信
            mentors = User.query.filter(User.role.in_(['mentor', 'admin'])).all()
            for mentor in mentors:
                create_notification(
                    user_id=mentor.id,
                    title='新しい報告が登録されました',
                    message=f'{mentee.name}さんが新しい週次報告を登録しました。',
                    notification_type='report_created',
                    related_id=report.id
                )
            
            # Ajaxリクエストかどうかをチェック
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': '週次報告が保存されました！'})
            else:
                flash('週次報告が保存されました！', 'success')
                return redirect(url_for('mentee_dashboard', mentee_id=mentee_id))
        except Exception as e:
            db.session.rollback()
            # Ajaxリクエストかどうかをチェック
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': f'報告の保存中にエラーが発生しました: {str(e)}'}), 500
            else:
                flash(f'報告の保存中にエラーが発生しました: {str(e)}', 'danger')
                # フォームの選択肢を再設定
                product_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).all()
                form.product_group.choices = [(0, '商品群を選択してください')] + [(pg.id, pg.name) for pg in product_groups]
    else:
        # バリデーションエラーがある場合
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # バリデーションエラーの詳細を取得
            error_messages = []
            for field, errors in form.errors.items():
                error_messages.extend(errors)
            return jsonify({'success': False, 'message': '入力内容にエラーがあります', 'errors': error_messages}), 400
        else:
            # フォームの選択肢を再設定
            product_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).all()
            form.product_group.choices = [(0, '商品群を選択してください')] + [(pg.id, pg.name) for pg in product_groups]
    
    # Todoリストを取得
    todo_list = MenteeTodoList.query.filter_by(mentee_id=mentee_id).first()
    
    # 商品群データを取得（画像表示用）
    product_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).all()
    
    # 商品群ごとの最新の進捗ステージを取得
    product_group_stages = get_product_group_latest_stages(mentee_id)
    
    return render_template('new_report.html', form=form, mentee=mentee, todo_list=todo_list, product_groups=product_groups, product_group_stages=product_group_stages)

@app.route('/report/<int:report_id>')
@login_required
def view_report(report_id):
    report = WeeklyReport.query.get_or_404(report_id)
    
    # セキュリティチェック：メンティは自分の報告のみ閲覧可能
    if current_user.role == 'mentee':
        if report.mentee.user_id != current_user.id:
            flash('アクセス権限がありません。', 'danger')
            return redirect(url_for('my_dashboard'))
    
    # 前週の報告を取得
    previous_week_start = report.week_start - timedelta(days=7)
    previous_report = WeeklyReport.query.filter_by(
        mentee_id=report.mentee_id, 
        week_start=previous_week_start
    ).first()
    
    # 商品群情報を取得（画像表示用）
    product_group = ProductGroup.query.filter_by(
        name=report.product_group,
        mentee_id=report.mentee_id
    ).first()
    
    # 追加の問いかけ回答をパース
    import ast
    try:
        additional_responses = ast.literal_eval(report.additional_responses) if report.additional_responses else {}
    except (ValueError, SyntaxError, TypeError):
        additional_responses = {}
    
    return render_template('view_report.html', report=report, previous_report=previous_report, additional_responses=additional_responses, product_group=product_group)

@app.route('/report/<int:report_id>/comment', methods=['GET', 'POST'])
@login_required
def add_mentor_comment(report_id):
    # メンター権限チェック
    if current_user.role not in ['mentor', 'admin']:
        flash('メンター権限が必要です。', 'danger')
        return redirect(url_for('index'))
    
    report = WeeklyReport.query.get_or_404(report_id)
    form = MentorCommentForm()
    
    if form.validate_on_submit():
        # 既存のコメントをチェック（1つの報告に1つのコメントのみ）
        existing_comment = MentorComment.query.filter_by(
            report_id=report_id, 
            mentor_id=current_user.id
        ).first()
        
        if existing_comment:
            # 既存のコメントを更新
            existing_comment.comment = form.comment.data
            existing_comment.created_at = datetime.utcnow()
        else:
            # 新しいコメントを作成
            comment = MentorComment(
                report_id=report_id,
                mentor_id=current_user.id,
                comment=form.comment.data
            )
            db.session.add(comment)
        
        db.session.commit()
        
        # メンティに通知を送信
        mentee_user = User.query.get(report.mentee.user_id)
        if mentee_user:
            create_notification(
                user_id=mentee_user.id,
                title='メンターからコメントが追加されました',
                message=f'{current_user.username}さんからコメントが追加されました。',
                notification_type='comment_added',
                related_id=report_id
            )
        
        flash('コメントが保存されました！', 'success')
        return redirect(url_for('view_report', report_id=report_id))
    
    # 追加の問いかけ回答をパース
    import ast
    try:
        additional_responses = ast.literal_eval(report.additional_responses) if report.additional_responses else {}
    except (ValueError, SyntaxError, TypeError):
        additional_responses = {}
    
    # Todoリストを取得
    todo_list = MenteeTodoList.query.filter_by(mentee_id=report.mentee_id).first()
    
    return render_template('add_mentor_comment.html', form=form, report=report, additional_responses=additional_responses, todo_list=todo_list)

@app.route('/mentee/profile', methods=['GET', 'POST'])
@login_required
def mentee_profile():
    """メンティプロファイル編集"""
    if current_user.role != 'mentee':
        flash('メンティ権限が必要です。', 'danger')
        return redirect(url_for('index'))
    
    mentee = Mentee.query.filter_by(user_id=current_user.id).first()
    if not mentee:
        flash('メンティプロファイルが見つかりません。', 'danger')
        return redirect(url_for('index'))
    
    form = MenteeProfileForm(obj=mentee)
    
    if form.validate_on_submit():
        mentee.name = form.name.data
        db.session.commit()
        flash('プロファイルが更新されました！', 'success')
        return redirect(url_for('mentee_dashboard', mentee_id=mentee.id))
    
    return render_template('mentee_profile.html', form=form, mentee=mentee)

@app.route('/report/<int:report_id>', methods=['DELETE'])
@login_required
def delete_report(report_id):
    try:
        report = WeeklyReport.query.get_or_404(report_id)
        
        # セキュリティチェック：メンティは自分の報告のみ削除可能
        if current_user.role == 'mentee':
            if report.mentee.user_id != current_user.id:
                return jsonify({
                    'success': False,
                    'message': 'アクセス権限がありません'
                }), 403
        
        mentee_id = report.mentee_id
        
        # 報告を削除
        db.session.delete(report)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '報告が削除されました'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        }), 500

@app.route('/create-sample-mentee', methods=['POST'])
@login_required
def create_sample_mentee():
    try:
        # ログインユーザーがメンティの場合、既存のメンティレコードを取得
        if current_user.role == 'mentee':
            existing_mentee = Mentee.query.filter_by(user_id=current_user.id).first()
            if existing_mentee:
                return jsonify({
                    'success': True,
                    'mentee_id': existing_mentee.id,
                    'message': '既存のメンティプロファイルを使用します'
                })
            else:
                # メンティレコードが存在しない場合は作成
                mentee = Mentee(
                    name=current_user.username,
                    email=current_user.email,
                    user_id=current_user.id
                )
                db.session.add(mentee)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'mentee_id': mentee.id,
                    'message': 'メンティプロファイルが作成されました'
                })
        else:
            # メンター・管理者の場合は、サンプルメンティを作成（デモ用）
            existing_mentee = Mentee.query.filter_by(email='sample@example.com').first()
            
            if existing_mentee:
                return jsonify({
                    'success': True,
                    'mentee_id': existing_mentee.id,
                    'message': '既存のサンプルメンティを使用します'
                })
            else:
                # 新しいサンプルメンティを作成
                sample_mentee = Mentee(
                    name='サンプルメンティ',
                    email='sample@example.com'
                )
                db.session.add(sample_mentee)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'mentee_id': sample_mentee.id,
                    'message': 'サンプルメンティが作成されました'
                })
    except Exception as e:
        # エラーの詳細をログに出力
        print(f"Error creating sample mentee: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        })

@app.route('/notifications')
@login_required
def get_notifications():
    """通知一覧を取得"""
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()
    
    notification_data = []
    for notification in notifications:
        notification_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.type,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%Y年%m月%d日 %H:%M'),
            'related_id': notification.related_id
        })
    
    return jsonify({
        'notifications': notification_data,
        'unread_count': Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    })

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """通知を既読にする"""
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if notification:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """全ての通知を既読にする"""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})

@app.route('/mentee/<int:mentee_id>/todo', methods=['GET', 'POST'])
@login_required
def manage_todo_list(mentee_id):
    """メンティのTodoリスト管理"""
    mentee = Mentee.query.get_or_404(mentee_id)
    
    # セキュリティチェック
    if current_user.role == 'mentee' and mentee.user_id != current_user.id:
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    elif current_user.role not in ['mentor', 'admin'] and current_user.role != 'mentee':
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    
    # 既存のTodoリストを取得または作成
    todo_list = MenteeTodoList.query.filter_by(mentee_id=mentee_id).first()
    if not todo_list:
        todo_list = MenteeTodoList(mentee_id=mentee_id)
        db.session.add(todo_list)
        db.session.commit()
    
    if request.method == 'POST':
        # Todoリストを更新
        print(f"DEBUG: Todoリスト保存開始 - mentee_id: {mentee_id}")
        print(f"DEBUG: フォームデータ: {dict(request.form)}")
        
        todo_list.senior_work_target = request.form.get('senior_work_target', '')
        todo_list.senior_work_actual = request.form.get('senior_work_actual', '')
        todo_list.ordered_products = request.form.get('ordered_products', '')
        todo_list.ordered_details = request.form.get('ordered_details', '')
        todo_list.pending_products = request.form.get('pending_products', '')
        todo_list.pending_details = request.form.get('pending_details', '')
        todo_list.unproposed_products = request.form.get('unproposed_products', '')
        todo_list.unproposed_details = request.form.get('unproposed_details', '')
        todo_list.updated_at = datetime.utcnow()
        
        print(f"DEBUG: 保存前のTodoリスト: senior_work_target='{todo_list.senior_work_target}', ordered_products='{todo_list.ordered_products}'")
        
        db.session.commit()
        
        print(f"DEBUG: Todoリスト保存完了")
        flash('Todoリストが更新されました！', 'success')
        return redirect(url_for('new_report', mentee_id=mentee_id))
    
    return render_template('manage_todo_list.html', mentee=mentee, todo_list=todo_list)

@app.route('/mentee/<int:mentee_id>/product-groups', methods=['GET', 'POST'])
@login_required
def manage_product_groups(mentee_id):
    """代表商品群管理"""
    mentee = Mentee.query.get_or_404(mentee_id)
    
    # セキュリティチェック
    if current_user.role == 'mentee' and mentee.user_id != current_user.id:
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    elif current_user.role not in ['mentor', 'admin'] and current_user.role != 'mentee':
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    
    form = ProductGroupForm()
    
    if form.validate_on_submit():
        # 画像ファイルを保存
        saved_images = []
        if form.images.data:
            files = request.files.getlist('images')
            saved_images = save_uploaded_files(files)
        
        # 新しい代表商品群を登録
        product_group = ProductGroup(
            name=form.name.data,
            description=form.description.data,
            images=json.dumps(saved_images) if saved_images else None,
            mentee_id=mentee_id
        )
        db.session.add(product_group)
        db.session.commit()
        flash('代表商品群が登録されました！', 'success')
        return redirect(url_for('manage_product_groups', mentee_id=mentee_id))
    
    # 既存の代表商品群を取得
    product_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).order_by(ProductGroup.created_at.desc()).all()
    
    return render_template('manage_product_groups.html', mentee=mentee, form=form, product_groups=product_groups)

@app.route('/product-group/<int:product_group_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product_group(product_group_id):
    """代表商品群編集"""
    product_group = ProductGroup.query.get_or_404(product_group_id)
    
    # セキュリティチェック
    if current_user.role == 'mentee' and product_group.mentee.user_id != current_user.id:
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    elif current_user.role not in ['mentor', 'admin'] and current_user.role != 'mentee':
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    
    form = ProductGroupEditForm(obj=product_group)
    
    if form.validate_on_submit():
        # 既存の画像を取得
        existing_images = []
        if product_group.images:
            try:
                existing_images = json.loads(product_group.images)
            except (json.JSONDecodeError, TypeError):
                existing_images = []
        
        # 新しい画像ファイルを保存
        new_images = []
        if form.images.data:
            files = request.files.getlist('images')
            new_images = save_uploaded_files(files)
        
        # 既存の画像と新しい画像を結合
        all_images = existing_images + new_images
        
        # 代表商品群名の変更前後を保持
        old_name = product_group.name
        new_name = form.name.data

        # 代表商品群を更新
        product_group.name = new_name
        product_group.description = form.description.data
        product_group.images = json.dumps(all_images) if all_images else None

        # 紐づく週次報告の product_group 名称を一括更新（表示から消えないよう同期）
        if old_name != new_name:
            WeeklyReport.query.filter_by(
                mentee_id=product_group.mentee_id,
                product_group=old_name
            ).update({WeeklyReport.product_group: new_name})

        db.session.commit()
        flash('代表商品群が更新されました！', 'success')
        return redirect(url_for('manage_product_groups', mentee_id=product_group.mentee_id))
    
    # 既存の画像を取得
    existing_images = []
    if product_group.images:
        try:
            existing_images = json.loads(product_group.images)
        except (json.JSONDecodeError, TypeError):
            existing_images = []
    
    return render_template('edit_product_group.html', 
                         form=form, 
                         product_group=product_group, 
                         existing_images=existing_images)

@app.route('/product-group/<int:product_group_id>/delete', methods=['POST'])
@login_required
def delete_product_group(product_group_id):
    """代表商品群削除"""
    product_group = ProductGroup.query.get_or_404(product_group_id)
    
    # セキュリティチェック
    if current_user.role == 'mentee' and product_group.mentee.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'アクセス権限がありません'}), 403
    elif current_user.role not in ['mentor', 'admin'] and current_user.role != 'mentee':
        return jsonify({'success': False, 'message': 'アクセス権限がありません'}), 403
    
    try:
        # 関連する週次報告を確認
        related_reports = WeeklyReport.query.filter_by(
            mentee_id=product_group.mentee_id,
            product_group=product_group.name
        ).all()
        
        if related_reports:
            # 関連する報告がある場合は警告メッセージを返す
            return jsonify({
                'success': False, 
                'message': f'この商品群に関連する週次報告が{len(related_reports)}件あります。先に報告を削除するか、商品群名を変更してください。'
            }), 400
        
        # 関連する画像ファイルを削除
        if product_group.images:
            try:
                image_filenames = json.loads(product_group.images)
                delete_uploaded_files(image_filenames)
            except (json.JSONDecodeError, TypeError):
                pass
        
        mentee_id = product_group.mentee_id
        product_group_name = product_group.name
        
        # 削除前の確認
        before_count = ProductGroup.query.filter_by(mentee_id=mentee_id).count()
        
        # 代表商品群を削除
        db.session.delete(product_group)
        db.session.flush()  # 変更をフラッシュして即座に反映
        
        # 削除の確認
        deleted_check = ProductGroup.query.get(product_group_id)
        if deleted_check is not None:
            raise Exception("削除が正常に完了しませんでした")
        
        db.session.commit()
        
        # 削除後の確認
        remaining_groups = ProductGroup.query.filter_by(mentee_id=mentee_id).all()
        after_count = len(remaining_groups)
        
        if after_count >= before_count:
            raise Exception("削除処理が正常に完了しませんでした")
        
        return jsonify({
            'success': True, 
            'message': f'代表商品群「{product_group_name}」が削除されました（削除前: {before_count}件 → 削除後: {after_count}件）'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'エラーが発生しました: {str(e)}'}), 500

@app.route('/uploads/product_groups/<filename>')
def uploaded_file(filename):
    """アップロードされた画像ファイルを提供"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/product-group/<int:product_group_id>/remove-image', methods=['POST'])
@login_required
def remove_product_group_image(product_group_id):
    """代表商品群の画像を削除"""
    product_group = ProductGroup.query.get_or_404(product_group_id)
    
    # セキュリティチェック
    if current_user.role == 'mentee' and product_group.mentee.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'アクセス権限がありません'}), 403
    elif current_user.role not in ['mentor', 'admin'] and current_user.role != 'mentee':
        return jsonify({'success': False, 'message': 'アクセス権限がありません'}), 403
    
    try:
        data = request.get_json()
        filename_to_remove = data.get('filename')
        
        if not filename_to_remove:
            return jsonify({'success': False, 'message': 'ファイル名が指定されていません'}), 400
        
        # 既存の画像リストを取得
        existing_images = []
        if product_group.images:
            try:
                existing_images = json.loads(product_group.images)
            except (json.JSONDecodeError, TypeError):
                existing_images = []
        
        # 指定されたファイルをリストから削除
        if filename_to_remove in existing_images:
            existing_images.remove(filename_to_remove)
            
            # ファイルを物理的に削除
            delete_uploaded_files([filename_to_remove])
            
            # データベースを更新
            product_group.images = json.dumps(existing_images) if existing_images else None
            db.session.commit()
            
            return jsonify({'success': True, 'message': '画像が削除されました'})
        else:
            return jsonify({'success': False, 'message': '指定されたファイルが見つかりません'}), 404
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'エラーが発生しました: {str(e)}'}), 500

@app.route('/mentee/<int:mentee_id>/product-group-analysis')
@login_required
def product_group_analysis(mentee_id):
    """商品群別詳細分析ページ"""
    mentee = Mentee.query.get_or_404(mentee_id)
    
    # セキュリティチェック
    if current_user.role == 'mentee' and mentee.user_id != current_user.id:
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    elif current_user.role not in ['mentor', 'admin'] and current_user.role != 'mentee':
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    
    # 期間パラメータを取得（デフォルトは12週間）
    weeks = request.args.get('weeks', 12, type=int)
    weeks = min(max(weeks, 1), 52)  # 1-52週間に制限
    
    # 商品群別進捗データを取得
    product_group_progress = get_product_group_progress(mentee_id, weeks)
    
    # 全期間の進捗データも取得（比較用）
    all_time_progress = get_product_group_progress(mentee_id, 52)
    
    # メンター・管理者の場合は全メンティリストを取得
    all_mentees = []
    if current_user.role in ['mentor', 'admin']:
        all_mentees = Mentee.query.order_by(Mentee.name).all()
    
    return render_template('product_group_analysis.html', 
                         mentee=mentee, 
                         product_group_progress=product_group_progress,
                         all_time_progress=all_time_progress,
                         selected_weeks=weeks,
                         all_mentees=all_mentees)

@app.route('/product-group/<int:product_group_id>/details')
@login_required
def product_group_details(product_group_id):
    """商品群詳細ページ"""
    product_group = ProductGroup.query.get_or_404(product_group_id)
    mentee = product_group.mentee
    
    # セキュリティチェック
    if current_user.role == 'mentee' and mentee.user_id != current_user.id:
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    elif current_user.role not in ['mentor', 'admin'] and current_user.role != 'mentee':
        flash('アクセス権限がありません。', 'danger')
        return redirect(url_for('my_dashboard'))
    
    # この商品群の報告を取得
    reports = WeeklyReport.query.filter_by(
        mentee_id=mentee.id,
        product_group=product_group.name
    ).order_by(WeeklyReport.report_date.desc()).all()
    
    # 商品群の進捗データを取得
    product_group_progress = get_product_group_progress(mentee.id, 52)
    current_progress = next((pg for pg in product_group_progress if pg['name'] == product_group.name), None)
    
    return render_template('product_group_details.html',
                         product_group=product_group,
                         mentee=mentee,
                         reports=reports,
                         current_progress=current_progress)

# 日報関連のルート
@app.route('/daily-report/generate/<int:weekly_report_id>')
@login_required
def generate_daily_report(weekly_report_id):
    """週次報告から日報を生成"""
    try:
        weekly_report = WeeklyReport.query.get_or_404(weekly_report_id)
        
        # 権限チェック
        if current_user.role not in ['admin'] and weekly_report.mentee.user_id != current_user.id:
            flash('この報告から日報を生成する権限がありません。', 'danger')
            return redirect(url_for('my_dashboard'))
        
        # 日報を生成
        generated_data = generate_daily_report_from_weekly(weekly_report)
        
        # フォームに初期値を設定
        form = DailyReportForm()
        form.title.data = generated_data['title']
        form.summary.data = generated_data['summary']
        form.content.data = generated_data['generated_content']
        
        return render_template('generate_daily_report.html', 
                             form=form, 
                             weekly_report=weekly_report,
                             generated_data=generated_data)
        
    except Exception as e:
        flash(f'日報の生成中にエラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('my_dashboard'))

@app.route('/daily-report/save', methods=['POST'])
@login_required
def save_daily_report():
    """日報を保存"""
    try:
        form = DailyReportForm()
        
        if form.validate_on_submit():
            # 週次報告IDを取得（hidden fieldから）
            weekly_report_id = request.form.get('weekly_report_id')
            weekly_report = None
            if weekly_report_id:
                weekly_report = WeeklyReport.query.get(int(weekly_report_id))
            
            # メンティを取得
            if weekly_report:
                mentee = weekly_report.mentee
            else:
                # 週次報告がない場合は、現在のユーザーに関連するメンティを取得
                mentee = Mentee.query.filter_by(user_id=current_user.id).first()
                if not mentee:
                    flash('メンティ情報が見つかりません。', 'danger')
                    return redirect(url_for('my_dashboard'))
            
            # 日報を作成
            daily_report = DailyReport(
                mentee_id=mentee.id,
                weekly_report_id=weekly_report.id if weekly_report else None,
                report_date=datetime.now(),
                title=form.title.data,
                summary=form.summary.data,
                generated_content=form.content.data,
                status='draft'
            )
            
            db.session.add(daily_report)
            db.session.commit()
            
            flash('日報を保存しました。', 'success')
            return redirect(url_for('view_daily_report', report_id=daily_report.id))
        else:
            flash('フォームの入力に問題があります。', 'danger')
            return redirect(url_for('my_dashboard'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'日報の保存中にエラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('my_dashboard'))

@app.route('/daily-report/<int:report_id>')
@login_required
def view_daily_report(report_id):
    """日報を表示"""
    try:
        daily_report = DailyReport.query.get_or_404(report_id)
        
        # 権限チェック
        if current_user.role not in ['admin', 'mentor'] and daily_report.mentee.user_id != current_user.id:
            flash('この日報を表示する権限がありません。', 'danger')
            return redirect(url_for('my_dashboard'))
        
        return render_template('view_daily_report.html', daily_report=daily_report)
        
    except Exception as e:
        flash(f'日報の表示中にエラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('my_dashboard'))

@app.route('/daily-reports/<int:mentee_id>')
@login_required
def list_daily_reports(mentee_id):
    """メンティの日報一覧を表示"""
    try:
        mentee = Mentee.query.get_or_404(mentee_id)
        
        # 権限チェック
        if current_user.role not in ['admin', 'mentor'] and mentee.user_id != current_user.id:
            flash('このメンティの日報を表示する権限がありません。', 'danger')
            return redirect(url_for('my_dashboard'))
        
        # 日報一覧を取得（新しい順）
        daily_reports = DailyReport.query.filter_by(mentee_id=mentee_id)\
                                        .order_by(DailyReport.report_date.desc())\
                                        .all()
        
        return render_template('list_daily_reports.html', 
                             mentee=mentee, 
                             daily_reports=daily_reports)
        
    except Exception as e:
        flash(f'日報一覧の表示中にエラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('my_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # 本番環境かどうかを環境変数で判定
    import os
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    port = int(os.environ.get('PORT', 5000))
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)