
function delete_confirm() {
    if (confirm("确定要删除吗?") == true){
        return true;
    }else{
        return false;
    }
}

document.getElementById("article_del").onclick=delete_confirm;
