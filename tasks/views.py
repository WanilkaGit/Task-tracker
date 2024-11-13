from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from tasks import models
from django.views.generic import ListView, DetailView, CreateView, View, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from tasks.mixins import UserIsOwnerMixin
from tasks.forms import TaskForm, TaskFilterForm, CommentForm
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login

# task_group = models.TaskGroup.objects.create(title="Without Group", description="Tasks that aren't have group")
# task_group.save()


class TaskListView(ListView):
    model = models.TaskGroup
    context_object_name = "groups"
    template_name = "tasks/task_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.GET.get("status", "")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = TaskFilterForm(self.request.GET)
        return context


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = models.Task
    context_object_name = "task"
    template_name = 'tasks/task_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = CommentForm()  # Додаємо порожню форму коментаря в контекст
        return context

    def post(self, request, *args, **kwargs):
        comment_form = CommentForm(request.POST, request.FILES)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.author = request.user
            comment.task = self.get_object()
            comment.save()
            return redirect('tasks:task-detail', pk=comment.task.pk)
        else:
            pass


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = models.Task
    fields = ['status', 'title', 'priority', 'description']
    template_name = 'tasks/create_task.html'

    def form_valid(self, form):
        form.instance.group_id = self.kwargs.get('group_id')
        form.instance.creator = self.request.user
        form.save()
        return super().form_valid(form)

    def get_success_url(self):
        task_group = get_object_or_404(models.TaskGroup, id=self.kwargs.get('group_id'))
        last_task = models.Task.objects.latest('id')
        task_group.tasks.add(last_task)
        task_group.save()
        return reverse_lazy('tasks:task-list')


class TaskGroupCreateView(LoginRequiredMixin, View):
    template_name = "tasks/taskgroup_form.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        title = request.POST.get("group-title")
        description = request.POST.get("group-description")
        task_group = models.TaskGroup.objects.create(title=title, description=description)
        task_group.save()
        return redirect("tasks:task-list")

class TogglePinGroupView(View):
    def post(self, request, group_id):
        group = get_object_or_404(models.TaskGroup, id=group_id)
        group.is_pinned = not group.is_pinned  # Перемикає стан закріплення
        group.save()
        return redirect(reverse('tasks:task-list'))


class DeleteSelectedGroupsView(View):
    def post(self, request):
        selected_groups = request.POST.getlist('selected_groups')
        models.TaskGroup.objects.filter(id__in=selected_groups).delete()
        return redirect(reverse_lazy('tasks:task-list'))


class TaskCompleteView(LoginRequiredMixin, UserIsOwnerMixin, View):
    def post(self, request, *args, **kwargs):
        task = self.get_object()
        task.status = "done"
        task.save()
        return HttpResponseRedirect(reverse_lazy("tasks:task-list"))

    def get_object(self):
        task_id = self.kwargs.get("pk")
        return get_object_or_404(models.Task, pk=task_id)


class TaskUpdateView(LoginRequiredMixin, UserIsOwnerMixin, UpdateView):
    model = models.Task
    form_class = TaskForm
    template_name = "tasks/task_update_form.html"
    success_url = reverse_lazy("tasks:task-list")


class TaskDeleteView(LoginRequiredMixin, UserIsOwnerMixin, DeleteView):
    model = models.Task
    success_url = reverse_lazy("tasks:task-list")
    template_name = "tasks/task_delete_confirmation.html"


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    model = models.Comment
    fields = ['content']
    template_name = 'tasks/edit_comment.html'

    def form_valid(self, form):
        comment = self.get_object()
        if comment.author != self.request.user:
            raise PermissionDenied("Ви не можете редагувати цей коментар.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('tasks:task_detail', kwargs={'pk': self.object.task.pk})


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = models.Comment
    template_name = 'tasks/delete_comment.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(author=self.request.user)

    def get_success_url(self):
        return reverse_lazy('tasks:task_detail', kwargs={'pk': self.object.task.pk})


class CommentLikeToggle(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        comment = get_object_or_404(models.Comment, pk=self.kwargs.get('pk'))
        like_qs = models.Like.objects.filter(comment=comment, user=request.user)
        if like_qs.exists():
            like_qs.delete()
        else:
            models.Like.objects.create(comment=comment, user=request.user)
        return HttpResponseRedirect(comment.get_absolute_url())


class CustomLoginView(LoginView):
    template_name = "tasks/login.html"
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    next_page = "tasks:login"


class RegisterView(CreateView):
    template_name = "tasks/register.html"
    form_class = UserCreationForm

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect(reverse_lazy("tasks:login"))
